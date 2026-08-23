import { useState } from "react"
import type { FormEvent } from "react"
import { useTranslation } from "react-i18next"

import {
  resetDailySettings,
  resetGameSettings,
  updateDailySettings,
  updateGameSettings,
} from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import type { DailySettingsOut, GameSettingsOut } from "../api/types/admin"
import { Button } from "../games/shared/Button"
import { Switch } from "../games/shared/Switch"
import { SettingAccordion } from "./SettingAccordion"
import { SettingInfo } from "./SettingInfo"

// Both setting labels and their help text live in two i18n namespaces each - admin.games.<ns>.*
// for the knobs a normal game already has (shared verbatim by the daily form below, since it's
// the exact same knob), and admin.daily.<ns>.* for the two daily-only ones (no_repeat_days/
// chain_length). A key that isn't in the first namespace comes back unchanged (i18next's fallback
// when nothing matches), so checking for that is enough to know to look in the second one instead.
function settingKey(t: (key: string) => string, key: string, namespace: "settings" | "settingsHelp"): string {
  const gamesKey = `admin.games.${namespace}.${key}`
  const value = t(gamesKey)
  return value === gamesKey ? t(`admin.daily.${namespace}.${key}`) : value
}

function settingLabel(t: (key: string) => string, key: string): string {
  return settingKey(t, key, "settings")
}

// Description + (for anything but a bool, where "range 0-1" is noise on a checkbox) a
// Default/range line composed from the DTO's own default/min_value/max_value - never hand-written
// per key, so it can't drift from a SettingSpec change.
function settingHelp(
  t: (key: string, options?: Record<string, unknown>) => string,
  setting: GameSettingsOut["settings"][number],
): string {
  const description = settingKey(t, setting.key, "settingsHelp")
  if (setting.value_type === "bool") return description
  const range = t("admin.games.settingsRangeTemplate", {
    default: setting.default,
    min: setting.min_value,
    max: setting.max_value,
  })
  return `${description}\n${range}`
}

// Special-cased instead of using the generic bool value_type's plain checkbox (below) - the two
// states here have their own vocabulary ("linear" vs. "streak-based"), which a generic
// checkbox-for-any-0/1-setting wouldn't know how to label. streak_scoring itself stays typed
// "int", not "bool" - see its SettingSpec in games/whos_that_person/settings.py.
function StreakScoringToggle({
  id,
  checked,
  onChange,
  helpText,
}: {
  id: string
  checked: boolean
  onChange: (checked: boolean) => void
  helpText: string
}) {
  const { t } = useTranslation()
  return (
    <label htmlFor={id} className="flex cursor-pointer items-center gap-3 text-sm font-semibold text-body">
      <Switch id={id} checked={checked} onChange={onChange} />
      {t(checked ? "admin.games.settings.streak_scoring_on" : "admin.games.settings.streak_scoring_off")}
      <SettingInfo helpText={helpText} />
    </label>
  )
}

interface AdminGameRowProps {
  gameType: string
  mode: string
  title: string
  settings: GameSettingsOut
  onUpdated: (updated: GameSettingsOut) => void
  // The same mode's daily config, rendered inline below the normal settings form (not a separate
  // accordion) so admins see both together.
  dailySettings: DailySettingsOut
  onDailyUpdated: (updated: DailySettingsOut) => void
}

function SettingsForm({
  idPrefix,
  fields,
  values,
  onChange,
  onSave,
  onReset,
  busy,
  error,
  saved,
}: {
  idPrefix: string
  fields: GameSettingsOut["settings"]
  values: Record<string, number>
  onChange: (key: string, value: number) => void
  onSave: (e: FormEvent) => void
  onReset: () => void
  busy: boolean
  error: string | null
  saved: boolean
}) {
  const { t } = useTranslation()
  return (
    <>
      <form onSubmit={onSave} className="flex flex-col gap-4">
        {fields.map((setting) =>
          setting.key === "streak_scoring" ? (
            <StreakScoringToggle
              key={setting.key}
              id={`${idPrefix}-${setting.key}`}
              checked={values[setting.key] === 1}
              onChange={(checked) => onChange(setting.key, checked ? 1 : 0)}
              helpText={settingHelp(t, setting)}
            />
          ) : setting.value_type === "bool" ? (
            <label
              key={setting.key}
              htmlFor={`${idPrefix}-${setting.key}`}
              className="flex cursor-pointer items-center gap-2.5 text-sm font-semibold text-body"
            >
              <input
                id={`${idPrefix}-${setting.key}`}
                type="checkbox"
                checked={values[setting.key] === 1}
                onChange={(e) => onChange(setting.key, e.target.checked ? 1 : 0)}
                className="h-4 w-4 accent-primary"
              />
              {settingLabel(t, setting.key)}
              <SettingInfo helpText={settingHelp(t, setting)} />
            </label>
          ) : (
            <div key={setting.key} className="flex flex-col gap-1.5">
              <label
                htmlFor={`${idPrefix}-${setting.key}`}
                className="flex items-center gap-1.5 text-sm font-semibold text-body"
              >
                {settingLabel(t, setting.key)}
                <SettingInfo helpText={settingHelp(t, setting)} />
              </label>
              <input
                id={`${idPrefix}-${setting.key}`}
                type="number"
                step={setting.value_type === "int" ? 1 : "any"}
                min={setting.min_value}
                max={setting.max_value}
                required
                value={values[setting.key]}
                onChange={(e) => onChange(setting.key, Number(e.target.value))}
                className="rounded-xl border border-line-soft bg-surface px-3.5 py-2.5 text-base text-ink outline-none transition-colors focus:border-primary"
              />
            </div>
          ),
        )}
        <div className="flex gap-3">
          <Button type="submit" variant="primary" className="flex-1 py-2.5" disabled={busy}>
            {t("auth.profile.save")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="flex-1 py-2.5"
            onClick={onReset}
            disabled={busy}
          >
            {t("admin.games.reset")}
          </Button>
        </div>
      </form>
      {error && <p className="mt-4 text-sm font-semibold text-rose-600">{error}</p>}
      {saved && !error && (
        <p className="mt-4 text-sm font-semibold text-emerald-600">{t("auth.profile.saved")}</p>
      )}
    </>
  )
}

// One numeric field per admin-configurable setting (services/game_settings.py's
// GAME_SETTING_SPECS), plus Save/reset-to-defaults. Nested under a per-game accordion, one row
// per mode. MoreOrLess's modes have no configurable
// settings today, so their rows just show a "nothing to configure" message instead of a form -
// the daily block below still renders regardless, since a daily config always has at least one
// setting (no_repeat_days or chain_length, see services/daily_settings.py).
export function AdminGameRow({
  gameType,
  mode,
  title,
  settings,
  onUpdated,
  dailySettings,
  onDailyUpdated,
}: AdminGameRowProps) {
  const { t } = useTranslation()
  const [values, setValues] = useState<Record<string, number>>(
    Object.fromEntries(settings.settings.map((s) => [s.key, s.value])),
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const [dailyEnabled, setDailyEnabled] = useState(dailySettings.enabled)
  const [dailyValues, setDailyValues] = useState<Record<string, number>>(
    Object.fromEntries(dailySettings.settings.map((s) => [s.key, s.value])),
  )
  const [dailyToggleBusy, setDailyToggleBusy] = useState(false)
  const [dailyFormBusy, setDailyFormBusy] = useState(false)
  const [dailyError, setDailyError] = useState<string | null>(null)
  const [dailySaved, setDailySaved] = useState(false)

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const updated = await updateGameSettings(gameType, mode, values)
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
      const reset = await resetGameSettings(gameType, mode)
      onUpdated(reset)
      setValues(Object.fromEntries(reset.settings.map((s) => [s.key, s.value])))
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  async function handleDailyToggle(checked: boolean) {
    setDailyEnabled(checked) // optimistic - reverted below on failure
    setDailyToggleBusy(true)
    setDailyError(null)
    try {
      const updated = await updateDailySettings(gameType, mode, { enabled: checked })
      onDailyUpdated(updated)
      setDailyEnabled(updated.enabled)
    } catch (err) {
      setDailyEnabled(!checked)
      setDailyError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setDailyToggleBusy(false)
    }
  }

  async function handleDailySave(e: FormEvent) {
    e.preventDefault()
    setDailyFormBusy(true)
    setDailyError(null)
    setDailySaved(false)
    try {
      const updated = await updateDailySettings(gameType, mode, { values: dailyValues })
      onDailyUpdated(updated)
      setDailyValues(Object.fromEntries(updated.settings.map((s) => [s.key, s.value])))
      setDailySaved(true)
    } catch (err) {
      setDailyError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setDailyFormBusy(false)
    }
  }

  async function handleDailyReset() {
    setDailyFormBusy(true)
    setDailyError(null)
    setDailySaved(false)
    try {
      const reset = await resetDailySettings(gameType, mode)
      onDailyUpdated(reset)
      setDailyEnabled(reset.enabled)
      setDailyValues(Object.fromEntries(reset.settings.map((s) => [s.key, s.value])))
    } catch (err) {
      setDailyError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setDailyFormBusy(false)
    }
  }

  return (
    <SettingAccordion nested title={title}>
      {settings.settings.length === 0 ? (
        <p className="text-sm text-faint">{t("admin.games.noSettings")}</p>
      ) : (
        <SettingsForm
          idPrefix={`${gameType}-${mode}`}
          fields={settings.settings}
          values={values}
          onChange={(key, value) => {
            setValues((prev) => ({ ...prev, [key]: value }))
            setSaved(false)
          }}
          onSave={handleSave}
          onReset={handleReset}
          busy={busy}
          error={error}
          saved={saved}
        />
      )}

      <hr className="my-4 border-line-soft" />
      <div className="flex flex-col gap-4">
        <label className="flex items-center gap-2.5 text-sm font-semibold text-body">
          <input
            type="checkbox"
            checked={dailyEnabled}
            disabled={dailyToggleBusy}
            onChange={(e) => handleDailyToggle(e.target.checked)}
            className="h-4 w-4 accent-primary"
          />
          {t("admin.daily.enabledLabel")}
        </label>

        <SettingsForm
          idPrefix={`${gameType}-${mode}-daily`}
          fields={dailySettings.settings}
          values={dailyValues}
          onChange={(key, value) => {
            setDailyValues((prev) => ({ ...prev, [key]: value }))
            setDailySaved(false)
          }}
          onSave={handleDailySave}
          onReset={handleDailyReset}
          busy={dailyFormBusy}
          error={dailyError}
          saved={dailySaved}
        />
      </div>
    </SettingAccordion>
  )
}
