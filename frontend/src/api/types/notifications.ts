// Mirrors backend/src/api/dto/notifications.py.

export interface NotificationPreferences {
  daily_reminders: boolean
  birthdays: boolean
  album_anniversary: boolean
  language: string
}

export interface SubscribeIn {
  endpoint: string
  keys: {
    p256dh: string
    auth: string
  }
}
