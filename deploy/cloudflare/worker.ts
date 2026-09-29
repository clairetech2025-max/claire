import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  CLAIRE_CONTAINER: DurableObjectNamespace<ClaireContainer>;
}

export class ClaireContainer extends Container {
  defaultPort = 7860;
  sleepAfter = "10m";
  enableInternet = true;
  envVars = {
    PORT: "7860",
    CLAIRE_PROVIDER: "nim",
    CLAIRE_PUBLIC_DEMO_BUILD: "1",
    CLAIRE_CREATOR_MODE_ENABLED: "1",
    CLAIRE_CORE_ENABLED: "false",
    CLAIRE_CORE_SHADOW_MODE: "true",
    CLAIRE_PROVIDER_TIMEOUT_SECONDS: "180",
    CLAIRE_GO_ADDR: "127.0.0.1:8080",
    LLM_URL: "http://127.0.0.1:8080",
    NVIDIA_NIM_BASE_URL: "https://integrate.api.nvidia.com/v1",
    NVIDIA_NIM_MODEL: "nvidia/nemotron-3-ultra-550b-a55b",
  };
}

function stripRuntimePrefix(request: Request): Request {
  const url = new URL(request.url);
  if (url.pathname === "/runtime") {
    url.pathname = "/";
  } else if (url.pathname.startsWith("/runtime/")) {
    url.pathname = url.pathname.slice("/runtime".length) || "/";
  }
  return new Request(url.toString(), request);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    return getContainer(env.CLAIRE_CONTAINER, "claire-staging").fetch(stripRuntimePrefix(request));
  },
};
