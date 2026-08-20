// Browser-API wrappers for Web Push - permission, subscribe/unsubscribe, and the base64url<->bytes
// conversion PushManager.subscribe's applicationServerKey needs. Kept free of any app-specific
// state (that's useNotificationSettings.ts) so these stay pure enough to unit test.

export type PushSupport = "unsupported" | "no-push-manager" | "denied" | "ready"

// Three independent feature-detects, checked in the order a real gap actually blocks the next
// one: no serviceWorker means no secure context at all (http://, not localhost); PushManager is
// missing on iOS Safari until the app is added to the home screen even though the SW itself
// registers fine there; permission can be denied independently of both.
export function getPushSupport(): PushSupport {
  if (!("serviceWorker" in navigator)) return "unsupported"
  if (!("PushManager" in window)) return "no-push-manager"
  if (Notification.permission === "denied") return "denied"
  return "ready"
}

// Standard base64url -> Uint8Array conversion (RFC 4648 §5, unpadded) - GET /config's
// push_public_key travels as base64url text; PushManager.subscribe's applicationServerKey wants
// raw bytes.
export function urlBase64ToUint8Array(base64Url: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64Url.length % 4)) % 4)
  const base64 = (base64Url + padding).replace(/-/g, "+").replace(/_/g, "/")
  // Global, not window.atob - works unchanged under vitest's default "node" environment (see
  // this file's own push.test.ts) as well as the real browser main thread this runs in.
  const raw = atob(base64)
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) {
    bytes[i] = raw.charCodeAt(i)
  }
  // `new Uint8Array(n)` infers Uint8Array<ArrayBufferLike>, which TS's DOM lib no longer accepts
  // where a BufferSource (applicationServerKey below) is expected - it's always a real
  // ArrayBuffer at runtime, never a SharedArrayBuffer, so this cast is exactly that gap.
  return bytes as Uint8Array<ArrayBuffer>
}

// requestPermission() must be called from inside a user gesture (§3.2, notably iOS) - this never
// wraps it in anything async-before-the-call, so callers must invoke it directly from a click
// handler, not after an intermediate await.
export function requestNotificationPermission(): Promise<NotificationPermission> {
  return Notification.requestPermission()
}

// Returns the existing subscription if the device already has one (idempotent - re-running the
// activation flow, e.g. after a preference change, never creates a second one for the same
// device).
export async function subscribePush(vapidPublicKey: string): Promise<PushSubscription> {
  const registration = await navigator.serviceWorker.ready
  const existing = await registration.pushManager.getSubscription()
  if (existing) return existing
  return registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
  })
}

// Best-effort - callers (logout, the settings "deactivate" flow) don't block on this failing.
export async function unsubscribePush(): Promise<void> {
  if (!("serviceWorker" in navigator)) return
  const registration = await navigator.serviceWorker.getRegistration()
  const subscription = await registration?.pushManager.getSubscription()
  await subscription?.unsubscribe()
}
