import { useState } from "react"
import type { FormEvent } from "react"
import { useTranslation } from "react-i18next"

import { resetGameSettings, updateGameSettings } from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import type { GameSettingsOut } from "../api/types"
import { Button } from "../games/shared/Button"
import { SettingAccordion } from "./SettingAccordion"

interface AdminGameRowProps {
  gameType: string
  title: string
  settings: GameSettingsOut
  onUpdated: (updated: GameSettingsOut) => void
}

// Admin feature (ADMIN-FEATURE.md point #4) - one numeric field per admin-configurable setting
// (services/game_settings.py's GAME_SETTING_SPECS), plus Save/reset-to-defaults. MoreOrLess has
// no configurable settings today, so its row just shows a "nothing to configure" message instead
// of an empty form.
export function AdminGameRow({ gameType, title, settings, onUpdated }: AdminGameRowProps) {
  const { t } = useTranslation()
  const [values, setValues] = useState<Record<string, number>>(
    Object.fromEntries(settings.settings.map((s) => [s.key, s.value])),
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const updated = await updateGameSettings(gameType, values)
      onUpdated(updated)
      setValues(Object.fromEntries(updated.settings.map((s) => [s.key, s.value])))
      setSaved(true)
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  async function handleReset() {
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const reset = await resetGameSettings(gameType)
      onUpdated(reset)
      setValues(Object.fromEntries(reset.settings.map((s) => [s.key, s.value])))
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  if (settings.settings.length === 0) {
    return (
      <SettingAccordion nested title={title}>
        <p className="text-sm text-faint">{t("admin.games.noSettings")}</p>
      </SettingAccordion>
    )
  }

  return (
    <SettingAccordion nested title={title}>
      <form onSubmit={handleSave} className="flex flex-col gap-4">
        {settings.settings.map((setting) => (
          <div key={setting.key} className="flex flex-col gap-1.5">
            <label htmlFor={`${gameType}-${setting.key}`} className="text-sm font-semibold text-body">
              {t(`admin.games.settings.${setting.key}`)}
            </label>
            <input
              id={`${gameType}-${setting.key}`}
              type="number"
              step={setting.value_type === "int" ? 1 : "any"}
              min={setting.min_value}
              max={setting.max_value}
              required
              value={values[setting.key]}
              onChange={(e) => {
                setValues((prev) => ({ ...prev, [setting.key]: Number(e.target.value) }))
                setSaved(false)
              }}
              className="rounded-xl border border-line-soft bg-surface px-3.5 py-2.5 text-base text-ink outline-none transition-colors focus:border-primary"
            />
          </div>
        ))}
        <div className="flex gap-3">
          <Button type="submit" variant="primary" className="flex-1 py-2.5" disabled={busy}>
            {t("auth.profile.save")}
          </Button>
          <Button type="button" variant="secondary" className="flex-1 py-2.5" onClick={handleReset} disabled={busy}>
            {t("admin.games.reset")}
          </Button>
        </div>
      </form>
      {error && <p className="mt-4 text-sm font-semibold text-rose-600">{error}</p>}
      {saved && !error && <p className="mt-4 text-sm font-semibold text-emerald-600">{t("auth.profile.saved")}</p>}
    </SettingAccordion>
  )
}
