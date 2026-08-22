// Standard base64url -> Uint8Array conversion (RFC 4648 §5, unpadded) - GET /config's
// push_public_key travels as base64url text; PushManager.subscribe's applicationServerKey wants
// raw bytes. Its own module, not push.ts, so it can be imported from both the main-thread world
// (push.ts, re-exported from here - dom lib, tsconfig.app.json) and the service worker world
// (sw.ts's pushsubscriptionchange handler - webworker lib, tsconfig.sw.json): those two are
// type-checked against different lib sets, and this is the one piece of push.ts's surface sw.ts
// also needs. atob/Uint8Array are the only globals it touches, present in both.
export function urlBase64ToUint8Array(base64Url: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64Url.length % 4)) % 4)
  const base64 = (base64Url + padding).replace(/-/g, "+").replace(/_/g, "/")
  // Global, not window.atob - works unchanged under vitest's default "node" environment (see
  // push.test.ts) as well as the real browser main thread/service worker this runs in.
  const raw = atob(base64)
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) {
    bytes[i] = raw.charCodeAt(i)
  }
  // `new Uint8Array(n)` infers Uint8Array<ArrayBufferLike>, which TS's DOM lib no longer accepts
  // where a BufferSource (applicationServerKey) is expected - it's always a real ArrayBuffer at
  // runtime, never a SharedArrayBuffer, so this cast is exactly that gap.
  return bytes as Uint8Array<ArrayBuffer>
}
