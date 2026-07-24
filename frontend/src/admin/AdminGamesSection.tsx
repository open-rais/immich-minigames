import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { listGameSettings } from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import type { GameSettingsOut } from "../api/types"
import { GAME_CATALOG } from "../games/catalog"
import { AdminGameRow } from "./AdminGameRow"

// Admin feature (ADMIN-FEATURE.md point #4) - content of the "Juegos" top-level accordion in
// AdminPage.tsx. Mounts lazily (SettingAccordion only mounts children on first expand). Fetches
// every game's settings in one request, then renders a nested row per GAME_CATALOG entry (the
// same source of truth already used elsewhere for game type/title) so a game with no persisted
// override yet still gets a row showing its defaults.
export function AdminGamesSection() {
  const { t } = useTranslation()
  const [settingsByType, setSettingsByType] = useState<Record<string, GameSettingsOut> | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listGameSettings()
      .then((list) => setSettingsByType(Object.fromEntries(list.map((s) => [s.game_type, s]))))
      .catch((err) => setError(apiErrorMessage(err) ?? t("auth.error.generic")))
  }, [t])

  function handleUpdated(updated: GameSettingsOut) {
    setSettingsByType((prev) => (prev ? { ...prev, [updated.game_type]: updated } : prev))
  }

  if (error) return <p className="text-sm font-semibold text-rose-600">{error}</p>
  if (!settingsByType) return <p className="text-sm text-faint">{t("admin.games.loading")}</p>

  return (
    <div>
      {GAME_CATALOG.map((game) => {
        const settings = settingsByType[game.gameType]
        if (!settings) return null
        return (
          <AdminGameRow
            key={game.gameType}
            gameType={game.gameType}
            title={t(game.gameTitleKey)}
            settings={settings}
            onUpdated={handleUpdated}
          />
        )
      })}
    </div>
  )
}
