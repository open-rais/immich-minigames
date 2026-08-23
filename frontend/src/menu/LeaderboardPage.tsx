import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { Navigate, useNavigate, useParams } from "react-router-dom"

import { getLeaderboard, personThumbnailUrl } from "../api/games"
import type { LeaderboardEntryOut, LeaderboardWindow } from "../api/types/leaderboard"
import { useAuth } from "../auth/useAuth"
import { GAME_CATALOG } from "../games/catalog"
import { BackButton } from "../games/shared/BackButton"
import { PersonAvatar } from "../games/shared/PersonAvatar"
import { SegmentedControl } from "../games/shared/SegmentedControl"
import { LeaderboardTitleNav } from "./LeaderboardTitleNav"
import { useLeaderboardNav } from "./leaderboardNav"

// Roadmap point F - top 15 per (gameType, mode), reached from that mode's idle/finished screens
// (see games/shared/GameScreens.tsx). The [‹] game [›] / [‹] mode [›] header (roadmap point k)
// walks every board in the app from here, daily ones included - see menu/leaderboardNav.ts.
export function LeaderboardPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { gameType, mode } = useParams<{ gameType: string; mode: string }>()
  const { user } = useAuth()
  const [window_, setWindow] = useState<LeaderboardWindow>("all")
  const [entries, setEntries] = useState<LeaderboardEntryOut[] | null>(null)

  const game = GAME_CATALOG.find((g) => g.gameType === gameType)
  const catalogMode = game?.modes.find((m) => m.mode === mode)
  // The category here is the game itself, so its own gameType is the category id.
  const nav = useLeaderboardNav(gameType ?? "", gameType ?? "", mode ?? "")

  useEffect(() => {
    if (!gameType || !mode) return
    let cancelled = false
    setEntries(null)
    getLeaderboard(gameType, mode, window_)
      .then(({ entries }) => {
        if (!cancelled) setEntries(entries)
      })
      .catch(() => {
        if (!cancelled) setEntries([])
      })
    return () => {
      cancelled = true
    }
  }, [gameType, mode, window_])

  if (!catalogMode || !game || !gameType || !mode) return <Navigate to="/" replace />

  const windowOptions: { value: LeaderboardWindow; label: string }[] = [
    { value: "all", label: t("leaderboard.window.all") },
    { value: "weekly", label: t("leaderboard.window.weekly") },
    { value: "daily", label: t("leaderboard.window.daily") },
  ]

  return (
    <div className="flex min-h-screen flex-col items-center gap-6 bg-app-bg px-6 py-10">
      <BackButton label={t("common.back")} onClick={() => navigate(`/${gameType}/${mode}`)} />

      <div className="mt-14 w-full max-w-xs md:mt-0">
        <h1 className="text-center text-3xl font-bold text-ink">{t("leaderboard.title")}</h1>
        <LeaderboardTitleNav
          nav={nav}
          gameTitle={t(game.gameTitleKey)}
          modeTitle={t(catalogMode.modeTitleKey)}
        />
      </div>

      <div className="w-full max-w-xs">
        <SegmentedControl options={windowOptions} value={window_} onChange={setWindow} />
      </div>

      <div className="w-full max-w-md rounded-3xl border border-line bg-surface p-4 shadow-card">
        {entries === null ? null : entries.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">{t("leaderboard.empty")}</p>
        ) : (
          <ol className="flex flex-col gap-1">
            {entries.map((entry) => (
              <li
                key={entry.rank}
                className={`flex items-center gap-3 rounded-2xl px-3 py-2 ${
                  user && entry.username === user.username ? "bg-primary/10" : ""
                }`}
              >
                <span className="w-6 flex-none text-center font-bold text-muted">{entry.rank}</span>
                <PersonAvatar
                  src={entry.skin_person_id ? personThumbnailUrl(entry.skin_person_id) : null}
                  alt=""
                />
                <span className="min-w-0 flex-1 truncate font-semibold text-ink">
                  {entry.username}
                </span>
                <span className="flex-none font-mono font-bold text-ink">{entry.best_score}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}
