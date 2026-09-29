import { Container, getContainer } from "@cloudflare/containers";
import { RUNTIME_PREFIX, rewriteForPrefix } from "./runtime_prefix";

// Edge twin of the Hugging Face Space. The container image is built from the
// same Space tree (see build_cloudflare_tree.sh), so behaviour is identical;
// this Durable Object adds what the Space disk gives HF for free: durable
// runtime state. The container restores the last committed snapshot before
// any service boots, and every completed turn is committed back here before
// the client sees the end of the response.

const PORT = 7860;
const INSTANCE = "claire-staging";
const TOKEN_HEADER = "X-CLAIRE-STATE-TOKEN";
const DIGEST_HEADER = "X-CLAIRE-STATE-SHA256";
const CHUNK_BYTES = 1024 * 1024; // below the 2 MiB DO storage value limit
const PUT_BATCH = 128; // max keys per storage.put()
const BOOT_TIMEOUT_MS = 240_000; // Go provider + ARE acceptance gate
const READ_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

// Same names as the Hugging Face Space secrets/variables (deploy/huggingface/claire.manifest.json).
const FORWARDED_SECRETS = [
  "CLAIRELLAMA",
  "NVIDIA_API_KEY",
  "CLAIRE_ARE_HMAC_KEY",
  "CLAIRE_TRAILLINK_HMAC_KEY",
  "CLAIRE_INTERNAL_OPERATOR_TOKEN",
  // Optional integrations (.env.example); forwarded only when set, as on HF.
  "ELEVENLABS_API_KEY", // CLAIRE's voice; without it the browser's default TTS voice is used
  "ELEVENLABS_VOICE_ID",
  "COURTLISTENER_API_KEY",
  "COURTLISTENER_TOKEN",
  "GEMINI_API_KEY",
  "CAP_API_KEY",
  "SEMANTIC_SCHOLAR_API_KEY",
  "CLAIRE_INGEST_TOKEN",
  "CLAIRE_ADMIN_ACTION_TOKEN",
  "HANDSHAKE_BROKER_SECRET",
  "CLAIRE_GOOGLE_OAUTH_TOKEN_JSON",
  "CLAIRE_GOOGLE_SERVICE_ACCOUNT_JSON",
] as const;
const FORWARDED_VARS = [
  "CLAIRE_PROVIDER",
  "CLAIRE_LOCAL_MODEL_ID",
  "CLAIRE_LLAMA_URL",
  "CLAIRE_PROVIDER_MAX_TOKENS",
  "CLAIRE_PROVIDER_TIMEOUT_SECONDS",
  "NVIDIA_NIM_BASE_URL",
  "NVIDIA_NIM_MODEL",
  "CLAIRE_PUBLIC_DEMO_BUILD",
  "CLAIRE_CREATOR_MODE_ENABLED",
  "CLAIRE_CORE_ENABLED",
  "CLAIRE_CORE_SHADOW_MODE",
  "CLAIRE_USER_TIMEZONE",
  "MAINTENANCE_MODE",
  "GEMINI_MODEL",
  "OPENALEX_MAILTO",
] as const;

type ForwardedName = (typeof FORWARDED_SECRETS)[number] | (typeof FORWARDED_VARS)[number];

export type Env = {
  CLAIRE_CONTAINER: DurableObjectNamespace<ClaireContainer>;
} & Partial<Record<ForwardedName, string>>;

interface StateHead {
  gen: number;
  chunks: number;
  bytes: number;
  sha256: string;
  committedAt: string;
}

interface BootSession {
  token: string;
  restored: boolean;
}

const HEAD_KEY = "state:head";
const SESSION_KEY = "state:session";
const EPOCH_KEY = "state:epoch";
// Bump to discard all durable edge state once, e.g. after rotating
// CLAIRE_TRAILLINK_HMAC_KEY (older Truth Spine records would no longer verify).
// 2: CLAIRE_TRAILLINK_HMAC_KEY set for the first time (2026-09-29).
const STATE_EPOCH = 2;
const chunkKey = (gen: number, index: number) => `state:${gen}:${index}`;

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function randomToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export class ClaireContainer extends Container<Env> {
  defaultPort = PORT;
  sleepAfter = "10m";
  enableInternet = true;

  private booting: Promise<void> | null = null;
  private commitChain: Promise<void> = Promise.resolve();

  constructor(ctx: DurableObjectState<{}>, env: Env) {
    super(ctx, env);
    // Any start that bypasses bootAndRestore() lacks a sync token and exits in
    // start.sh, so an unrestored container can never serve or be snapshotted.
    this.envVars = this.runtimeEnv();
  }

  private runtimeEnv(token?: string): Record<string, string> {
    const vars: Record<string, string> = { PORT: String(PORT), CLAIRE_STATE_RESTORE: "do" };
    for (const name of [...FORWARDED_VARS, ...FORWARDED_SECRETS]) {
      const value = this.env[name];
      if (value) vars[name] = value;
    }
    if (token) vars.CLAIRE_STATE_SYNC_TOKEN = token;
    return vars;
  }

  override async fetch(request: Request): Promise<Response> {
    await this.ensureRestored();
    if (READ_METHODS.has(request.method) || request.headers.get("Upgrade")?.toLowerCase() === "websocket") {
      return this.containerFetch(request, PORT);
    }
    return this.withCommitBarrier(await this.containerFetch(request, PORT));
  }

  override async onActivityExpired(): Promise<void> {
    try {
      await this.commitSnapshot();
    } catch (error) {
      console.error("final state commit before sleep failed", error);
    }
    await this.stop();
  }

  // ---- restore -----------------------------------------------------------

  private async ensureRestored(): Promise<void> {
    const [state, session, epoch] = await Promise.all([
      this.getState(),
      this.ctx.storage.get<BootSession>(SESSION_KEY),
      this.ctx.storage.get<number>(EPOCH_KEY),
    ]);
    const live = state.status === "running" || state.status === "healthy";
    const current = epoch === STATE_EPOCH;
    if (current && live && session?.restored) return;
    this.booting ??= (current ? this.bootAndRestore(live) : this.resetAndBoot(live)).finally(() => {
      this.booting = null;
    });
    return this.booting;
  }

  private async resetAndBoot(live: boolean): Promise<void> {
    if (live) await this.destroy(); // drop the old container before it can commit again
    const keys = [...(await this.ctx.storage.list({ prefix: "state:" })).keys()];
    for (let i = 0; i < keys.length; i += PUT_BATCH) {
      await this.ctx.storage.delete(keys.slice(i, i + PUT_BATCH));
    }
    await this.ctx.storage.put(EPOCH_KEY, STATE_EPOCH);
    console.log(`edge state reset to epoch ${STATE_EPOCH}; ${keys.length} keys discarded`);
    await this.bootAndRestore(false);
  }

  private async bootAndRestore(live: boolean): Promise<void> {
    if (live) {
      // Running without a confirmed restore (e.g. a boot interrupted mid-way):
      // its state is not authoritative, so replace it.
      await this.destroy();
    }
    const token = randomToken();
    await this.ctx.storage.put<BootSession>(SESSION_KEY, { token, restored: false });
    await this.startAndWaitForPorts({
      ports: PORT,
      startOptions: { envVars: this.runtimeEnv(token) },
      cancellationOptions: { portReadyTimeoutMS: BOOT_TIMEOUT_MS },
    });

    const snapshot = await this.loadSnapshot();
    const headers: Record<string, string> = { [TOKEN_HEADER]: token };
    if (snapshot) headers[DIGEST_HEADER] = snapshot.sha256;
    const restore = await this.containerFetch(
      new Request("http://container/internal/state/import", {
        method: "POST",
        headers,
        body: snapshot?.bytes ?? new Uint8Array(),
      }),
      PORT,
    );
    if (!restore.ok) {
      throw new Error(`state restore failed: ${restore.status} ${await restore.text()}`);
    }

    await this.waitForRuntime();
    await this.ctx.storage.put<BootSession>(SESSION_KEY, { token, restored: true });
    // Capture what boot wrote (ARE acceptance record) as the first commit.
    await this.commitSnapshot();
  }

  private async waitForRuntime(): Promise<void> {
    const deadline = Date.now() + BOOT_TIMEOUT_MS;
    while (Date.now() < deadline) {
      try {
        // The restore server answers 503 on /health; the real runtime answers 200.
        const res = await this.containerFetch(new Request("http://container/health"), PORT);
        if (res.ok) return;
      } catch {
        // port briefly closed while start.sh swaps restore server -> runtime
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    throw new Error("CLAIRE runtime did not become healthy after state restore");
  }

  private async loadSnapshot(): Promise<{ bytes: Uint8Array; sha256: string } | null> {
    const head = await this.ctx.storage.get<StateHead>(HEAD_KEY);
    if (!head) return null;
    const keys = Array.from({ length: head.chunks }, (_, i) => chunkKey(head.gen, i));
    const bytes = new Uint8Array(head.bytes);
    let offset = 0;
    for (let i = 0; i < keys.length; i += PUT_BATCH) {
      const batch = await this.ctx.storage.get<Uint8Array>(keys.slice(i, i + PUT_BATCH));
      for (const key of keys.slice(i, i + PUT_BATCH)) {
        const chunk = batch.get(key);
        if (!chunk) throw new Error(`state snapshot gen ${head.gen} is missing ${key}`);
        bytes.set(chunk, offset);
        offset += chunk.byteLength;
      }
    }
    if ((await sha256Hex(bytes)) !== head.sha256) {
      throw new Error(`state snapshot gen ${head.gen} failed integrity check`);
    }
    return { bytes, sha256: head.sha256 };
  }

  // ---- commit barrier ----------------------------------------------------

  private async withCommitBarrier(response: Response): Promise<Response> {
    if (response.status >= 500 || response.status === 101) return response;
    if (!response.body) {
      // No body to hold back: commit before handing the response over.
      await this.commitSnapshot();
      return response;
    }
    // Stream through as-is; the final flush waits for the commit, so the
    // client sees the turn end only once its state is durable.
    const barrier = new TransformStream<Uint8Array, Uint8Array>({
      flush: () => this.commitSnapshot(),
    });
    return new Response(response.body.pipeThrough(barrier), response);
  }

  private commitSnapshot(): Promise<void> {
    const run = this.commitChain.then(() => this.captureSnapshot());
    this.commitChain = run.catch((error) => console.error("state commit failed", error));
    return run;
  }

  private async captureSnapshot(): Promise<void> {
    const [session, state] = await Promise.all([
      this.ctx.storage.get<BootSession>(SESSION_KEY),
      this.getState(),
    ]);
    // Never overwrite durable state from an unrestored container, and never
    // wake a stopped one just to export (the next request restores it first).
    if (!session?.restored || !(state.status === "running" || state.status === "healthy")) return;

    const res = await this.containerFetch(
      new Request("http://container/internal/state/export", { headers: { [TOKEN_HEADER]: session.token } }),
      PORT,
    );
    if (!res.ok) throw new Error(`state export failed: ${res.status}`);
    const bytes = new Uint8Array(await res.arrayBuffer());
    const sha256 = await sha256Hex(bytes);
    const claimed = res.headers.get(DIGEST_HEADER);
    if (claimed && claimed !== sha256) throw new Error("state export digest mismatch");

    const previous = await this.ctx.storage.get<StateHead>(HEAD_KEY);
    if (previous?.sha256 === sha256) return;

    const gen = (previous?.gen ?? 0) + 1;
    const chunks: [string, Uint8Array][] = [];
    for (let offset = 0, i = 0; offset < bytes.byteLength; offset += CHUNK_BYTES, i++) {
      chunks.push([chunkKey(gen, i), bytes.slice(offset, offset + CHUNK_BYTES)]);
    }
    for (let i = 0; i < chunks.length; i += PUT_BATCH) {
      await this.ctx.storage.put(Object.fromEntries(chunks.slice(i, i + PUT_BATCH)));
    }
    // Commit point: the head flips to the new generation only once all its chunks exist.
    await this.ctx.storage.put<StateHead>(HEAD_KEY, {
      gen,
      chunks: chunks.length,
      bytes: bytes.byteLength,
      sha256,
      committedAt: new Date().toISOString(),
    });
    await this.deleteStaleChunks(gen);
  }

  private async deleteStaleChunks(currentGen: number): Promise<void> {
    const stale = [...(await this.ctx.storage.list({ prefix: "state:" })).keys()].filter((key) => {
      const gen = Number(key.split(":")[1]);
      return Number.isInteger(gen) && gen !== currentGen;
    });
    for (let i = 0; i < stale.length; i += PUT_BATCH) {
      await this.ctx.storage.delete(stale.slice(i, i + PUT_BATCH));
    }
  }
}

function stripRuntimePrefix(request: Request): { forwarded: Request; prefixed: boolean } {
  const url = new URL(request.url);
  const prefixed = url.pathname === RUNTIME_PREFIX || url.pathname.startsWith(`${RUNTIME_PREFIX}/`);
  if (prefixed) url.pathname = url.pathname.slice(RUNTIME_PREFIX.length) || "/";
  return { forwarded: new Request(url.toString(), request), prefixed };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { forwarded, prefixed } = stripRuntimePrefix(request);
    if (new URL(forwarded.url).pathname.startsWith("/internal/state/")) {
      // State sync is DO <-> container only; never reachable from the internet.
      return new Response(JSON.stringify({ status: "not_found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }
    const response = await getContainer(env.CLAIRE_CONTAINER, INSTANCE).fetch(forwarded);
    // clairesystems.ai/runtime/*: keep the GUI's root-relative calls (chat,
    // CLAIRE TV, uploads, voice) inside the route. workers.dev serves at root.
    return prefixed ? rewriteForPrefix(response) : response;
  },
} satisfies ExportedHandler<Env>;
