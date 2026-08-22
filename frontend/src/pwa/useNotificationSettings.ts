import { useCallback, useEffect, useState } from "react"

import { getConfig } from "../api/config"
import {
  getNotificationPreferences,
  sendTestNotification,
  subscribeToPush,
  updateNotificationPreferences,
} from "../api/notifications"
import type { NotificationPreferences } from "../api/types/notifications"
import i18n from "../i18n"
import { getPushSupport, requestNotificationPermission, subscribePush } from "./push"
import type { PushSupport } from "./push"
import { unsubscribeDeviceEverywhere } from "./unsubscribeDevice"

const DEFAULT_PREFERENCES: NotificationPreferences = {
  daily_reminders: false,
  birthdays: false,
  album_anniversary: false,
  language: "en",
}

type ToggleKey = "daily_reminders" | "birthdays" | "album_anniversary"

export interface NotificationSettingsState {
  support: PushSupport
  // null while /config hasn't answered yet or push isn't configured server-side - the settings
  // card renders nothing in either case (config.ts's own convention, see useImmichLinks).
  pushPublicKey: string | null
  preferences: NotificationPreferences | null
  subscribed: boolean
  busy: boolean
  activationError: boolean
  testError: boolean
  activate: () => Promise<void>
  deactivate: () => Promise<void>
  setToggle: (key: ToggleKey, value: boolean) => Promise<void>
  sendTest: () => Promise<void>
}

export function useNotificationSettings(): NotificationSettingsState {
  const [support, setSupport] = useState<PushSupport>(() => getPushSupport())
  const [pushPublicKey, setPushPublicKey] = useState<string | null>(null)
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null)
  const [subscribed, setSubscribed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [activationError, setActivationError] = useState(false)
  const [testError, setTestError] = useState(false)

  useEffect(() => {
    getConfig()
      .then((config) => setPushPublicKey(config.push_public_key))
      .catch(() => setPushPublicKey(null))
  }, [])

  useEffect(() => {
    if (!pushPublicKey) return
    getNotificationPreferences()
      .then(setPreferences)
      .catch(() => setPreferences(null))
  }, [pushPublicKey])

  useEffect(() => {
    if (support !== "ready" || !("serviceWorker" in navigator)) return
    navigator.serviceWorker
      .getRegistration()
      .then((registration) => registration?.pushManager.getSubscription())
      .then((subscription) => setSubscribed(subscription != null))
      .catch(() => setSubscribed(false))
  }, [support])

  const activate = useCallback(async () => {
    if (!pushPublicKey) return
    setBusy(true)
    setActivationError(false)
    try {
      const permission = await requestNotificationPermission()
      setSupport(getPushSupport())
      if (permission !== "granted") return

      const subscription = await subscribePush(pushPublicKey)
      const json = subscription.toJSON()
      if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
        throw new Error("Subscription is missing endpoint/keys")
      }
      await subscribeToPush({ endpoint: json.endpoint, keys: { p256dh: json.keys.p256dh, auth: json.keys.auth } })

      // Stamps the account's current language so a future push can be composed in it (the
      // service worker has no access to localStorage/i18next - see api/dto/notifications.py's
      // language field). Doesn't re-sync if the user changes language later in this same
      // session without touching a notification toggle again - a minor gap, not worth coupling
      // the general language selector to this feature for.
      //
      // Only when `preferences` is already loaded - PUT is a full replace (no partial-update
      // endpoint exists), so falling back to DEFAULT_PREFERENCES here (all three toggles off)
      // would silently wipe out real saved ones whenever the GET above hasn't resolved yet or
      // failed (offline, a 500). The account's language just stays whatever it already was until
      // the next real preference change (setToggle below always has real preferences to build
      // from) - a smaller gap than clobbering someone's settings.
      if (preferences) {
        const saved = await updateNotificationPreferences({ ...preferences, language: i18n.language })
        setPreferences(saved)
      }
      setSubscribed(true)
    } catch {
      setActivationError(true)
    } finally {
      setBusy(false)
    }
  }, [pushPublicKey, preferences])

  const deactivate = useCallback(async () => {
    setBusy(true)
    try {
      await unsubscribeDeviceEverywhere()
      setSubscribed(false)
    } finally {
      setBusy(false)
    }
  }, [])

  const setToggle = useCallback(
    async (key: ToggleKey, value: boolean) => {
      const base = preferences ?? DEFAULT_PREFERENCES
      const next = { ...base, [key]: value, language: i18n.language }
      setPreferences(next)
      try {
        const saved = await updateNotificationPreferences(next)
        setPreferences(saved)
      } catch {
        setPreferences(base)
      }
    },
    [preferences],
  )

  const sendTest = useCallback(async () => {
    setBusy(true)
    setTestError(false)
    try {
      await sendTestNotification()
    } catch {
      setTestError(true)
    } finally {
      setBusy(false)
    }
  }, [])

  return {
    support,
    pushPublicKey,
    preferences,
    subscribed,
    busy,
    activationError,
    testError,
    activate,
    deactivate,
    setToggle,
    sendTest,
  }
}
