import { useTranslation } from "react-i18next"

import { Button } from "../games/shared/Button"
import { Switch } from "../games/shared/Switch"
import { useNotificationSettings } from "../pwa/useNotificationSettings"
import { SettingCard } from "./SettingsPage"

const SUPPORT_NOTE_KEY: Record<"unsupported" | "no-push-manager" | "denied", string> = {
  unsupported: "settings.notifications.unsupported",
  "no-push-manager": "settings.notifications.noPushManager",
  denied: "settings.notifications.denied",
}

function ToggleRow({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string
  checked: boolean
  disabled: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <label className="flex items-center justify-between gap-3 py-2 text-[15px] text-body">
      <span>{label}</span>
      <Switch checked={checked} disabled={disabled} onChange={onChange} />
    </label>
  )
}

// Renders nothing at all when GET /config's push_public_key is null - the backend has no VAPID
// keys configured, so there's no "disabled" state worth showing, unlike the three client-side
// support gaps below (unsupported/no-push-manager/denied), which do render, disabled, with an
// explanatory note.
export function NotificationsCard() {
  const { t } = useTranslation()
  const state = useNotificationSettings()

  if (!state.pushPublicKey) return null

  const togglesDisabled = state.support !== "ready" || state.busy || !state.subscribed

  return (
    <SettingCard label={t("settings.notifications.title")}>
      {state.support !== "ready" && (
        <p className="mb-3 text-sm text-faint">{t(SUPPORT_NOTE_KEY[state.support])}</p>
      )}

      <div className="divide-y divide-line-soft">
        <ToggleRow
          label={t("settings.notifications.enablePush")}
          checked={state.subscribed}
          disabled={state.support !== "ready" || state.busy}
          onChange={(value) => void (value ? state.activate() : state.deactivate())}
        />
        <ToggleRow
          label={t("settings.notifications.dailyReminders")}
          checked={state.preferences?.daily_reminders ?? false}
          disabled={togglesDisabled}
          onChange={(value) => void state.setToggle("daily_reminders", value)}
        />
        <ToggleRow
          label={t("settings.notifications.birthdays")}
          checked={state.preferences?.birthdays ?? false}
          disabled={togglesDisabled}
          onChange={(value) => void state.setToggle("birthdays", value)}
        />
        <ToggleRow
          label={t("settings.notifications.albumAnniversary")}
          checked={state.preferences?.album_anniversary ?? false}
          disabled={togglesDisabled}
          onChange={(value) => void state.setToggle("album_anniversary", value)}
        />
      </div>
      {state.activationError && (
        <p className="mt-2 text-sm text-danger">{t("settings.notifications.activationError")}</p>
      )}

      <Button
        variant="secondary"
        className="mt-4 w-full px-4 py-2.5"
        disabled={!state.subscribed || state.busy}
        onClick={() => void state.sendTest()}
      >
        {t("settings.notifications.sendTest")}
      </Button>
      {state.testError && <p className="mt-2 text-sm text-danger">{t("settings.notifications.testError")}</p>}
    </SettingCard>
  )
}
