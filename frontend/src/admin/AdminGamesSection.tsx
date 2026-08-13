import { useMemo } from "react"
import { useTranslation } from "react-i18next"

import {
  DAILY_SETTINGS_KEY,
  GAME_SETTINGS_KEY,
  listDailySettings,
  listGameSettings,
} from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import { updateCached, useLiveQuery } from "../api/queryCache"
import type { DailySettingsOut, GameSettingsOut } from "../api/types/admin"
import { GAME_CATALOG } from "../games/catalog"
import { AdminGameRow } from "./AdminGameRow"
import { SettingAccordion } from "./SettingAccordion"

// Same "gameType:mode" convention as menu/GameSection.tsx's `records` Map.
function settingsKey(gameType: string, mode: string): string {
  return `${gameType}:${mode}`
}

// Read-modify-write helper for both list-of-settings caches below.
function replaceByKey<T extends { game_type: string; mode: string }>(
  list: T[] | undefined,
  updated: T,
): T[] {
  const prev = list ?? []
  const idx = prev.findIndex((s) => s.game_type === updated.game_type && s.mode === updated.mode)
  if (idx === -1) return [...prev, updated]
  const next = [...prev]
  next[idx] = updated
  return next
}

// One top-level accordion per game, each with one nested row per mode. Fetches every
// (game_type, mode)'s settings in one request, then renders a nested row per GAME_CATALOG mode
// (the same source of truth already used elsewhere for game/mode titles) so a mode with no
// persisted override yet still gets a row showing its defaults. Also fetches the daily config for
// every mode alongside the normal settings (one extra request, same shape) and threads it into
// each AdminGameRow, which
// renders the "Activar juego diario" toggle + daily-only settings inline below the normal ones.
export function AdminGamesSection() {
  const { t } = useTranslation()
  const gameSettingsQuery = useLiveQuery<GameSettingsOut[]>(GAME_SETTINGS_KEY, listGameSettings)
  const dailySettingsQuery = useLiveQuery<DailySettingsOut[]>(DAILY_SETTINGS_KEY, listDailySettings)

  const settingsByKey = useMemo(
    () =>
      gameSettingsQuery.value &&
      Object.fromEntries(gameSettingsQuery.value.map((s) => [settingsKey(s.game_type, s.mode), s])),
    [gameSettingsQuery.value],
  )
  const dailyByKey = useMemo(
    () =>
      dailySettingsQuery.value &&
      Object.fromEntries(
        dailySettingsQuery.value.map((d) => [settingsKey(d.game_type, d.mode), d]),
      ),
    [dailySettingsQuery.value],
  )

  function handleUpdated(updated: GameSettingsOut) {
    updateCached<GameSettingsOut[]>(GAME_SETTINGS_KEY, (prev) => replaceByKey(prev, updated))
  }

  function handleDailyUpdated(updated: DailySettingsOut) {
    updateCached<DailySettingsOut[]>(DAILY_SETTINGS_KEY, (prev) => replaceByKey(prev, updated))
  }

  // Doesn't swallow the error (queryCache.ts's LiveQuery contract): a load failure still shows a
  // real message, same as before this migration - but a value already sitting in cache from an
  // earlier visit stays visible underneath it instead of being replaced by the error.
  const loadError = gameSettingsQuery.error ?? dailySettingsQuery.error
  const errorMessage = loadError ? (apiErrorMessage(loadError) ?? t("auth.error.generic")) : null

  if (!settingsByKey || !dailyByKey) {
    if (errorMessage) return <p className="text-sm font-semibold text-rose-600">{errorMessage}</p>
    return <p className="text-sm text-faint">{t("admin.games.loading")}</p>
  }

  return (
    <>
      {errorMessage && <p className="mb-4 text-sm font-semibold text-rose-600">{errorMessage}</p>}
      {GAME_CATALOG.map((game) => (
        <SettingAccordion
          key={game.gameType}
          title={t(game.gameTitleKey)}
          description={t("admin.games.description")}
        >
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
