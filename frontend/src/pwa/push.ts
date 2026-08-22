// Browser-API wrappers for Web Push - permission and subscribe. Kept free of any app-specific
// state (that's useNotificationSettings.ts) so these stay pure enough to unit test.

export { urlBase64ToUint8Array } from "./base64"
import { urlBase64ToUint8Array } from "./base64"

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

// requestPermission() must be called from inside a user gesture (notably iOS Safari, which
// silently ignores the call otherwise) - this never wraps it in anything async-before-the-call,
// so callers must invoke it directly from a click handler, not after an intermediate await.
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
