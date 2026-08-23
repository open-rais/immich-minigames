import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { getDailyStatus } from "../api/daily"
import { apiErrorMessage } from "../api/errors"
import { getGame } from "../api/games"
import { useLiveQuery } from "../api/queryCache"
import type { GameOut } from "../api/types/common"
import type { DailyModeStatusOut, DailyStatusOut } from "../api/types/daily"
import { findCatalogMode, GAME_CATALOG } from "../games/catalog"
import { buildDailyShareAllMessage } from "../games/shared/dailyShareText"
import { ShareModal } from "../games/shared/ShareModal"
import { DAILY_STATUS_KEY } from "../games/shared/useGameSession"
import { isCollapsed, setCollapsed } from "./collapsedSections"
import { DailyCountdown } from "./DailyCountdown"
import { ModeCard } from "./ModeCard"

// Not a game's own gameType (no game is literally named "daily") - the fixed id this section
// persists its collapsed state under, same idea as GameSection.tsx using game.gameType.
const SECTION_ID = "daily"

function ShareIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <line x1="8.6" y1="10.6" x2="15.4" y2="6.4" />
      <line x1="8.6" y1="13.4" x2="15.4" y2="17.6" />
    </svg>
  )
}

// "Daily" menu section: same collapsible-group shape as a normal GameSection (chevron
// + title, grid-rows collapse animation, see menu/GameSection.tsx), but listing every enabled
// daily mode instead of one game's own modes, with a countdown to the next reset next to the
// title. Renders nothing once loaded if no mode is enabled - an empty section header
// would be worse than no section.
export function DailySection() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { state, refresh } = useLiveQuery<DailyStatusOut>(DAILY_STATUS_KEY, getDailyStatus)
  // "loading" has no value at all; "error" may or may not carry a stale one - see QueryState's
  // own doc comment (queryCache.ts) for why the caller, not the hook, decides what to do with that.
  const status = state.status === "loading" ? undefined : state.value
  // Lazy initializer - reads localStorage once, not on every render.
  const [expanded, setExpanded] = useState(() => !isCollapsed(SECTION_ID))
  const [shareBusy, setShareBusy] = useState(false)
  const [shareText, setShareText] = useState<string | null>(null)

  // Reserves this section's space from first paint instead of popping in once getDailyStatus()
  // resolves (a stutter that shifts every GameSection below it down) - same header shape and a
  // ModeCard-shaped placeholder grid, so there's no layout jump once the real content lands.
  if (!status) {
    if (state.status === "error") {
      return (
        <section>
          <div className="mb-1 flex items-center gap-2">
            <h2 className="text-3xl font-bold text-ink md:text-4xl">{t("daily.title")}</h2>
          </div>
          <hr className="mb-6 border-line" />
          <p className="text-sm text-body">
            {apiErrorMessage(state.error) ?? t("common.error.message")}
          </p>
          <button
            type="button"
            onClick={refresh}
            className="mt-2 text-sm font-semibold text-primary underline"
          >
            {t("common.error.retry")}
          </button>
        </section>
      )
    }
    return (
      <section className="animate-pulse">
        <div className="mb-1 flex items-center gap-2">
          <div className="h-5 w-5 flex-none rounded bg-line-soft" />
          <div className="h-8 w-40 rounded bg-line-soft md:h-9 md:w-48" />
        </div>
        <hr className="mb-6 border-line" />
        <div className="grid grid-cols-1 gap-2 pb-1 md:grid-cols-4 md:gap-4 lg:grid-cols-5 xl:grid-cols-6">
          {Array.from({ length: 4 }, (_, i) => (
            <div
              key={i}
              className="flex w-full items-center gap-4 p-2 md:flex-col md:items-stretch md:gap-3 md:p-3"
            >
              <div className="h-16 w-16 flex-none rounded-lg bg-line-soft md:aspect-square md:h-auto md:w-full md:rounded-xl" />
              <div className="min-w-0 flex-1 md:w-full md:flex-none">
                <div className="h-4 w-3/4 rounded bg-line-soft" />
                <div className="mt-2 h-3 w-1/2 rounded bg-line-soft" />
              </div>
            </div>
          ))}
        </div>
      </section>
    )
  }

  if (status.modes.length === 0) return null

  function subtitleFor(modeStatus: DailyModeStatusOut): string {
    if (modeStatus.status === "finished")
      return t("mainMenu.bestScore", { score: modeStatus.score ?? 0 })
    if (modeStatus.status === "in_progress") return t("common.continueCta")
    return t("mainMenu.notPlayed")
  }

  // A combined "share all results" summary line - only offered once every enabled mode has been
  // played, fetching each one's full GameOut (rounds)
  // on demand rather than keeping them all loaded just in case.
  const allFinished = status.modes.every((m) => m.status === "finished")

  function toggle() {
    setExpanded((e) => {
      const next = !e
      setCollapsed(SECTION_ID, !next)
      return next
    })
  }

  async function handleShareAll() {
    if (!status) return
    setShareBusy(true)
    try {
      const entries = await Promise.all(
        status.modes.map(
          async (
            modeStatus,
          ): Promise<{ gameTitle: string; modeTitle: string; game: GameOut } | null> => {
            if (!modeStatus.game_id) return null
            const catalogGame = GAME_CATALOG.find((g) => g.gameType === modeStatus.game_type)
            const catalogMode = findCatalogMode(modeStatus.game_type, modeStatus.mode)
            const game = await getGame(modeStatus.game_id)
            return {
              gameTitle: catalogGame ? t(catalogGame.gameTitleKey) : modeStatus.game_type,
              modeTitle: catalogMode ? t(catalogMode.modeTitleKey) : modeStatus.mode,
              game,
            }
          },
        ),
      )
      const nonNull = entries.filter(
        (e): e is { gameTitle: string; modeTitle: string; game: GameOut } => e !== null,
      )
      const link = `${window.location.origin}/`
      setShareText(buildDailyShareAllMessage(t, nonNull, link))
    } catch {
      // best-effort - same silent-fail convention as this section's own load() above.
    } finally {
      setShareBusy(false)
    }
  }

  return (
    <section>
      <div className="mb-1 flex flex-wrap items-center gap-3">
        <button type="button" onClick={toggle} className="flex items-center gap-2 text-left">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`flex-none text-ink transition-transform duration-300 ease-out ${expanded ? "" : "-rotate-90"}`}
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
          <h2 className="text-3xl font-bold text-ink md:text-4xl">{t("daily.title")}</h2>
        </button>
        {/* Keyed by resets_at so a day rollover's re-fetch remounts the countdown - its offset/
            fired refs are fixed at mount, so without the remount it would stay frozen at 00:00:00
            even though the cards themselves already switched to the new day. */}
        <DailyCountdown
          key={status.resets_at}
          resetsAt={status.resets_at}
          serverNow={status.server_now}
          onExpire={refresh}
        />
        {allFinished && (
          <button
            type="button"
            onClick={handleShareAll}
            disabled={shareBusy}
            aria-label={t("daily.share.button")}
            // inline-flex items-center justify-center: without it the inline <svg> sits per the
            // default inline-baseline box model, which leaves asymmetric space below it, so the
            // icon reads off-center inside the hover circle.
            className="ml-auto flex flex-none items-center justify-center rounded-full p-2 text-ink transition-colors hover:bg-hover-tint disabled:opacity-50"
          >
            <ShareIcon />
          </button>
        )}
      </div>
      <hr className="mb-6 border-line" />

      {/* Same grid-rows collapse trick as menu/GameSection.tsx. */}
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
      >
        <div className="overflow-hidden">
          <div className="grid grid-cols-1 gap-2 pb-1 md:grid-cols-4 md:gap-4 lg:grid-cols-5 xl:grid-cols-6">
            {status.modes.map((modeStatus) => {
              const catalogGame = GAME_CATALOG.find((g) => g.gameType === modeStatus.game_type)
              const catalogMode = findCatalogMode(modeStatus.game_type, modeStatus.mode)
              if (!catalogGame || !catalogMode) return null
              return (
                <ModeCard
                  key={`${modeStatus.game_type}:${modeStatus.mode}`}
                  // Cards from different games sit in one ungrouped grid here (unlike
                  // GameSection.tsx, where the game name is the section header) - so each card
                  // needs its own game name for context.
                  title={`${t(catalogGame.gameTitleKey)} - ${t(catalogMode.modeTitleKey)}`}
                  coverUrl={catalogMode.coverUrl}
                  subtitle={subtitleFor(modeStatus)}
                  onClick={() => navigate(`/daily/${modeStatus.game_type}/${modeStatus.mode}`)}
                />
              )
            })}
          </div>
        </div>
      </div>

      {shareText && <ShareModal text={shareText} onClose={() => setShareText(null)} />}
    </section>
  )
}
