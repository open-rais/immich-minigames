import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom"

import { getDailyLeaderboard } from "../api/daily"
import { personThumbnailUrl } from "../api/games"
import type { LeaderboardEntryOut } from "../api/types/leaderboard"
import { useAuth } from "../auth/useAuth"
import { GAME_CATALOG } from "../games/catalog"
import { BackButton } from "../games/shared/BackButton"
import { GameModeSubtitle } from "../games/shared/GameModeSubtitle"
import { PersonAvatar } from "../games/shared/PersonAvatar"

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function shiftDate(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

// Roadmap #G, F5 - /daily/:gameType/:mode/leaderboard. Close variant of menu/LeaderboardPage.tsx
// (same entry-list/row shape) with a [<] {date} [>] navigator instead of the all/weekly/daily
// SegmentedControl - a daily leaderboard is scoped to one specific day's challenge, not a rolling
// window. The right arrow disables once past today, since there's nothing to navigate to yet.
export function DailyLeaderboardPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { gameType, mode } = useParams<{ gameType: string; mode: string }>()
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const date = searchParams.get("date") || todayIso()
  const [entries, setEntries] = useState<LeaderboardEntryOut[] | null>(null)

  const game = GAME_CATALOG.find((g) => g.gameType === gameType)
  const catalogMode = game?.modes.find((m) => m.mode === mode)

  useEffect(() => {
    if (!gameType || !mode) return
    let cancelled = false
    setEntries(null)
    getDailyLeaderboard(gameType, mode, date)
      .then(({ entries }) => {
        if (!cancelled) setEntries(entries)
      })
      .catch(() => {
        if (!cancelled) setEntries([])
      })
    return () => {
      cancelled = true
    }
  }, [gameType, mode, date])

  if (!catalogMode || !game || !gameType || !mode) return <Navigate to="/" replace />

  const isToday = date >= todayIso()

  return (
    <div className="flex min-h-screen flex-col items-center gap-6 bg-app-bg px-6 py-10">
      <BackButton label={t("common.back")} onClick={() => navigate(`/daily/${gameType}/${mode}`)} />

      <div className="mt-14 text-center md:mt-0">
        <h1 className="text-3xl font-bold text-ink">{t("leaderboard.title")}</h1>
        <GameModeSubtitle
          gameTitle={t(game.gameTitleKey)}
          modeTitle={t(catalogMode.modeTitleKey)}
        />
      </div>

      <div className="flex w-full max-w-xs items-center justify-between">
        <button
          type="button"
          onClick={() => setSearchParams({ date: shiftDate(date, -1) })}
          className="rounded-full p-2 text-xl text-ink transition-colors hover:bg-hover-tint"
          aria-label={t("daily.leaderboard.previousDay")}
        >
          ‹
        </button>
        <span className="font-mono text-sm font-semibold text-ink">{date}</span>
        <button
          type="button"
          onClick={() => !isToday && setSearchParams({ date: shiftDate(date, 1) })}
          disabled={isToday}
          className="rounded-full p-2 text-xl text-ink transition-colors hover:bg-hover-tint disabled:opacity-30 disabled:hover:bg-transparent"
          aria-label={t("daily.leaderboard.nextDay")}
        >
          ›
        </button>
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
