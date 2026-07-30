import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { listDailySettings, listGameSettings } from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import type { DailySettingsOut, GameSettingsOut } from "../api/types"
import { GAME_CATALOG } from "../games/catalog"
import { AdminGameRow } from "./AdminGameRow"
import { SettingAccordion } from "./SettingAccordion"

// Same "gameType:mode" convention as menu/GameSection.tsx's `records` Map.
function settingsKey(gameType: string, mode: string): string {
  return `${gameType}:${mode}`
}

// Roadmap #f - one top-level accordion per game (replacing the single shared "Juegos" wrapper
// AdminPage.tsx used to render around this component), each with one nested row per mode instead
// of the old one-row-per-game_type. Fetches every (game_type, mode)'s settings in one request,
// then renders a nested row per GAME_CATALOG mode (the same source of truth already used
// elsewhere for game/mode titles) so a mode with no persisted override yet still gets a row
// showing its defaults. Roadmap #G - also fetches the daily config for every mode alongside the
// normal settings (one extra request, same shape) and threads it into each AdminGameRow, which
// renders the "Activar juego diario" toggle + daily-only settings inline below the normal ones.
export function AdminGamesSection() {
  const { t } = useTranslation()
  const [settingsByKey, setSettingsByKey] = useState<Record<string, GameSettingsOut> | null>(null)
  const [dailyByKey, setDailyByKey] = useState<Record<string, DailySettingsOut> | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([listGameSettings(), listDailySettings()])
      .then(([settings, daily]) => {
        setSettingsByKey(Object.fromEntries(settings.map((s) => [settingsKey(s.game_type, s.mode), s])))
        setDailyByKey(Object.fromEntries(daily.map((d) => [settingsKey(d.game_type, d.mode), d])))
      })
      .catch((err) => setError(apiErrorMessage(err) ?? t("auth.error.generic")))
  }, [t])

  function handleUpdated(updated: GameSettingsOut) {
    setSettingsByKey((prev) => (prev ? { ...prev, [settingsKey(updated.game_type, updated.mode)]: updated } : prev))
  }

  function handleDailyUpdated(updated: DailySettingsOut) {
    setDailyByKey((prev) => (prev ? { ...prev, [settingsKey(updated.game_type, updated.mode)]: updated } : prev))
  }

  if (error) return <p className="text-sm font-semibold text-rose-600">{error}</p>
  if (!settingsByKey || !dailyByKey) return <p className="text-sm text-faint">{t("admin.games.loading")}</p>

  return (
    <>
      {GAME_CATALOG.map((game) => (
        <SettingAccordion key={game.gameType} title={t(game.gameTitleKey)} description={t("admin.games.description")}>
          {game.modes.map((mode) => {
            const settings = settingsByKey[settingsKey(game.gameType, mode.mode)]
            const daily = dailyByKey[settingsKey(game.gameType, mode.mode)]
            if (!settings || !daily) return null
            return (
              <AdminGameRow
                key={mode.mode}
                gameType={game.gameType}
                mode={mode.mode}
                title={t(mode.modeTitleKey)}
                settings={settings}
                onUpdated={handleUpdated}
                dailySettings={daily}
                onDailyUpdated={handleDailyUpdated}
              />
            )
          })}
        </SettingAccordion>
      ))}
    </>
  )
}
