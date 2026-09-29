// CLAIRE's GUI is written for a site root (fetch("/reply"), fetch("/tv/action"),
// <img src="/static/...">), which is how Hugging Face serves it. At
// clairesystems.ai/runtime those root-relative URLs would leave the Worker
// route, so chat, CLAIRE TV, uploads and voice would all break. Rather than
// fork the GUI, pages served under the prefix are rewritten here.

export const RUNTIME_PREFIX = "/runtime";

// Runs in the browser before any GUI script. Routes every same-origin,
// root-relative URL the GUI creates at runtime through the prefix.
export const BROWSER_SHIM = `(() => {
  const P = ${JSON.stringify(RUNTIME_PREFIX)};
  const fix = (u) => {
    if (typeof u !== "string" || !u.startsWith("/") || u.startsWith("//")) return u;
    return u === P || u.startsWith(P + "/") || u.startsWith(P + "?") ? u : P + u;
  };
  const fixUrl = (u) => (u instanceof URL && u.origin === location.origin ? new URL(fix(u.pathname) + u.search + u.hash, u) : u);
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    if (typeof input === "string") return nativeFetch(fix(input), init);
    if (input instanceof URL) return nativeFetch(fixUrl(input), init);
    if (input instanceof Request) {
      const url = new URL(input.url);
      if (url.origin === location.origin && !url.pathname.startsWith(P + "/") && url.pathname !== P) {
        return nativeFetch(new Request(P + url.pathname + url.search, input), init);
      }
    }
    return nativeFetch(input, init);
  };
  const open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) { return open.call(this, method, fix(url), ...rest); };
  if (window.EventSource) {
    const ES = window.EventSource;
    window.EventSource = function (url, config) { return new ES(fix(url), config); };
    window.EventSource.prototype = ES.prototype;
  }
  const ATTRS = { src: 1, href: 1, action: 1, poster: 1 };
  const ELEMENTS = ["HTMLImageElement", "HTMLMediaElement", "HTMLVideoElement", "HTMLSourceElement", "HTMLIFrameElement", "HTMLScriptElement", "HTMLAnchorElement", "HTMLLinkElement", "HTMLFormElement", "HTMLEmbedElement", "HTMLTrackElement"];
  for (const Ctor of ELEMENTS.map((name) => window[name]).filter(Boolean)) {
    for (const name of ["src", "href", "action", "poster"]) {
      const desc = Object.getOwnPropertyDescriptor(Ctor.prototype, name);
      if (!desc || !desc.set) continue;
      Object.defineProperty(Ctor.prototype, name, { ...desc, set(value) { desc.set.call(this, fix(value)); } });
    }
  }
  const setAttribute = Element.prototype.setAttribute;
  Element.prototype.setAttribute = function (name, value) {
    return setAttribute.call(this, name, ATTRS[String(name).toLowerCase()] ? fix(value) : value);
  };
  // Markup inserted via innerHTML (e.g. CLAIRE TV evidence) bypasses the setters above.
  const sweep = (node) => {
    if (node.nodeType !== 1) return;
    for (const el of [node, ...node.querySelectorAll("[src],[href],[action],[poster]")]) {
      for (const name of Object.keys(ATTRS)) {
        const value = el.getAttribute && el.getAttribute(name);
        const fixed = fix(value);
        if (value && fixed !== value) setAttribute.call(el, name, fixed);
      }
    }
  };
  new MutationObserver((records) => {
    for (const r of records) {
      if (r.type === "attributes") sweep(r.target);
      else r.addedNodes.forEach(sweep);
    }
  }).observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: Object.keys(ATTRS) });
})();`;

function prefixed(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return value;
  if (value === RUNTIME_PREFIX || value.startsWith(`${RUNTIME_PREFIX}/`)) return value;
  return RUNTIME_PREFIX + value;
}

class AttributePrefixer {
  constructor(private readonly names: string[]) {}
  element(element: Element) {
    for (const name of this.names) {
      const value = element.getAttribute(name);
      const fixed = prefixed(value);
      if (fixed !== null && fixed !== value) element.setAttribute(name, fixed);
    }
  }
}

/** Make a GUI response served at /runtime/* self-consistent under that prefix. */
export function rewriteForPrefix(response: Response): Response {
  const headers = new Headers(response.headers);
  const location = headers.get("Location");
  if (location) headers.set("Location", prefixed(location) ?? location);
  const rehomed = new Response(response.body, { status: response.status, statusText: response.statusText, headers });

  const type = headers.get("Content-Type") || "";
  if (!type.includes("text/html") || !response.body) return rehomed;
  return new HTMLRewriter()
    .on("head", {
      element(head) {
        head.prepend(`<script>${BROWSER_SHIM}</script>`, { html: true });
      },
    })
    .on("[src]", new AttributePrefixer(["src"]))
    .on("[href]", new AttributePrefixer(["href"]))
    .on("form[action]", new AttributePrefixer(["action"]))
    .on("[poster]", new AttributePrefixer(["poster"]))
    .transform(rehomed);
}
