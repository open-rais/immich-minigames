import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { getRecentGames } from "../api/games"
import type { RecentGameOut } from "../api/types/common"
import { findCatalogMode, GAME_CATALOG } from "../games/catalog"
import { Button } from "../games/shared/Button"

type LoadState =
  { status: "loading" } | { status: "error" } | { status: "ready"; games: RecentGameOut[] }

interface RecentGamesModalProps {
  onClose: () => void
}

// Roadmap #e - profile "Ver juegos" modal: the last 5 games (finished or abandoned - never a
// still-active one, see GamesService.get_recent_games) of the logged-in account, each linking to
// its rounds view (roadmap #10, already built). Visual shell copied from games/shared/
// ConfirmExitModal.tsx's overlay/card pattern; loading/error/ready state machine modeled on
// games/rounds/RoundsPage.tsx.
export function RecentGamesModal({ onClose }: RecentGamesModalProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [state, setState] = useState<LoadState>({ status: "loading" })

  useEffect(() => {
    let cancelled = false
    getRecentGames()
      .then((games) => {
        if (!cancelled) setState({ status: "ready", games })
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" })
      })
    return () => {
      cancelled = true
    }
  }, [])

  function goToRounds(game: RecentGameOut) {
    onClose()
    navigate(`/${game.game_type}/${game.mode}/game/${game.id}/rounds`)
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-ink/40 px-6"
      onClick={onClose}
    >
      <div
        className="max-h-[80vh] w-full max-w-md overflow-y-auto rounded-2xl border border-line-soft bg-surface p-6 shadow-card"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-ink">{t("auth.profile.recentGames.title")}</h2>

        {state.status === "loading" && (
          <p className="mt-4 text-sm text-muted">{t("auth.profile.recentGames.loading")}</p>
        )}
        {state.status === "error" && (
          <p className="mt-4 text-sm text-muted">{t("common.error.message")}</p>
        )}
        {state.status === "ready" && state.games.length === 0 && (
          <p className="mt-4 text-sm text-muted">{t("auth.profile.recentGames.empty")}</p>
        )}
        {state.status === "ready" && state.games.length > 0 && (
          <ul className="mt-4 flex flex-col gap-2">
            {state.games.map((game) => {
              const catalogGame = GAME_CATALOG.find((g) => g.gameType === game.game_type)
              const catalogMode = findCatalogMode(game.game_type, game.mode)
              return (
                <li key={game.id}>
                  <button
                    type="button"
                    onClick={() => goToRounds(game)}
                    className="flex w-full items-center gap-3 rounded-xl border border-line-soft p-3 text-left transition-colors hover:bg-hover-tint"
                  >
                    {catalogMode?.coverUrl ? (
                      <img
                        src={catalogMode.coverUrl}
                        alt=""
                        className="h-10 w-10 flex-none rounded-lg object-cover"
                      />
                    ) : (
                      <div className="h-10 w-10 flex-none rounded-lg bg-primary" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-1.5 truncate text-sm font-semibold text-ink">
                        <span className="truncate">
                          {catalogGame && catalogMode
                            ? `${t(catalogGame.gameTitleKey)} · ${t(catalogMode.modeTitleKey)}`
                            : game.game_type}
                        </span>
                        {game.is_daily && (
                          <span className="flex-none rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-bold text-primary">
                            {t("auth.profile.recentGames.daily")}
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted">
                        {t("auth.profile.recentGames.score", { score: game.score })}
                        {" · "}
                        {t(
                          game.finished
                            ? "auth.profile.recentGames.finished"
                            : "auth.profile.recentGames.abandoned",
                        )}
                      </p>
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        )}

        <Button variant="secondary" className="mt-6 w-full py-2.5" onClick={onClose}>
          {t("common.back")}
        </Button>
      </div>
    </div>
  )
}
