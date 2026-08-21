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

export async function subscribeToPush(body: SubscribeIn): Promise<void> {
  await apiClient.post("/notifications/subscriptions", body)
}

export async function unsubscribeFromPush(endpoint: string): Promise<void> {
  await apiClient.delete("/notifications/subscriptions", { data: { endpoint } })
}

export async function sendTestNotification(): Promise<void> {
  await apiClient.post("/notifications/test")
}
