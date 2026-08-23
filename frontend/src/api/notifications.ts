import { apiClient } from "./client"
import type { NotificationPreferences, SubscribeIn } from "./types/notifications"

export async function getNotificationPreferences(): Promise<NotificationPreferences> {
  const { data } = await apiClient.get<NotificationPreferences>("/notifications/preferences")
  return data
}

export async function updateNotificationPreferences(
  body: NotificationPreferences,
): Promise<NotificationPreferences> {
  const { data } = await apiClient.put<NotificationPreferences>("/notifications/preferences", body)
  return data
}

// Partial update (only `language`) - unlike the PUT above, which replaces every field. Lets the
// app's one language selector (settings/SettingsPage.tsx) sync this without a GET-then-PUT that
// risks clobbering real toggles if the GET hasn't resolved yet or fails.
export async function setNotificationLanguage(language: string): Promise<NotificationPreferences> {
  const { data } = await apiClient.patch<NotificationPreferences>("/notifications/preferences/language", {
    language,
  })
  return data
}

export async function subscribeToPush(body: SubscribeIn): Promise<void> {
  await apiClient.post("/notifications/subscriptions", body)
}

export async function unsubscribeFromPush(endpoint: string): Promise<void> {
  await apiClient.delete("/notifications/subscriptions", { data: { endpoint } })
}

export async function sendTestNotification(): Promise<void> {
  await apiClient.post("/notifications/test")
}
