import { unsubscribeFromPush } from "../api/notifications"

// Unsubscribes this device on both sides - browser first, then backend, with the endpoint read
// *before* unsubscribing (a PushSubscription that's already been told to unsubscribe() no longer
// reports its own endpoint, so reading it after would always send an empty DELETE). Shared by
// useNotificationSettings.ts's own deactivate() and auth/AuthProvider.tsx's logout() (not a
// component, can't use the hook) - both best-effort, never throws.
export async function unsubscribeDeviceEverywhere(): Promise<void> {
  if (!("serviceWorker" in navigator)) return
  try {
    const registration = await navigator.serviceWorker.getRegistration()
    const subscription = await registration?.pushManager.getSubscription()
    if (!subscription) return
    const endpoint = subscription.endpoint
    await subscription.unsubscribe()
    await unsubscribeFromPush(endpoint)
  } catch {
    // Best-effort - a stale subscription/DB row left behind is a nuisance, never a reason to
    // block logout or the settings page's own deactivate button.
  }
}
