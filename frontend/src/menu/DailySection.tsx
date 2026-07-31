import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { getDailyStatus } from "../api/daily"
import { getGame } from "../api/games"
import type { GameOut } from "../api/types/common"
import type { DailyModeStatusOut, DailyStatusOut } from "../api/types/daily"
import { findCatalogMode } from "../games/catalog"
import { buildDailyShareAllMessage } from "../games/shared/dailyShareText"
import { ShareModal } from "../games/shared/ShareModal"
import { DailyCountdown } from "./DailyCountdown"
import { ModeCard } from "./ModeCard"

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

// Roadmap #G - "Daily" menu section: same collapsible-group shape as a normal GameSection (chevron
// + title, grid-rows collapse animation, see menu/GameSection.tsx), but listing every enabled
// daily mode instead of one game's own modes, with a countdown to the next reset next to the title
// (decision [G]). Renders nothing once loaded if no mode is enabled - an empty section header
// would be worse than no section.
export function DailySection() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [status, setStatus] = useState<DailyStatusOut | null>(null)
  const [expanded, setExpanded] = useState(true)
  const [shareBusy, setShareBusy] = useState(false)
  const [shareText, setShareText] = useState<string | null>(null)

  function load() {
    getDailyStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
  }

  useEffect(() => {
    load()
  }, [])

  if (!status || status.modes.length === 0) return null

  function subtitleFor(modeStatus: DailyModeStatusOut): string {
    if (modeStatus.status === "finished")
      return t("mainMenu.bestScore", { score: modeStatus.score ?? 0 })
    if (modeStatus.status === "in_progress") return t("common.continueCta")
    return t("mainMenu.notPlayed")
  }

  // Roadmap #G, F6 - "Si se comparte total: Todos resumidos a una linea" (docs/TODO/ROADMAP.md) -
  // only offered once every enabled mode has been played, fetching each one's full GameOut (rounds)
  // on demand rather than keeping them all loaded just in case.
  const allFinished = status.modes.every((m) => m.status === "finished")

  async function handleShareAll() {
    if (!status) return
    setShareBusy(true)
    try {
      const entries = await Promise.all(
        status.modes.map(
          async (modeStatus): Promise<{ modeTitle: string; game: GameOut } | null> => {
            if (!modeStatus.game_id) return null
            const catalogMode = findCatalogMode(modeStatus.game_type, modeStatus.mode)
            const game = await getGame(modeStatus.game_id)
            return { modeTitle: catalogMode ? t(catalogMode.modeTitleKey) : modeStatus.mode, game }
          },
        ),
      )
      const nonNull = entries.filter((e): e is { modeTitle: string; game: GameOut } => e !== null)
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
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-2 text-left"
        >
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
          onExpire={load}
        />
        {allFinished && (
          <button
            type="button"
            onClick={handleShareAll}
            disabled={shareBusy}
            aria-label={t("daily.share.button")}
            className="ml-auto flex-none rounded-full p-2 text-ink transition-colors hover:bg-hover-tint disabled:opacity-50"
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
              const catalogMode = findCatalogMode(modeStatus.game_type, modeStatus.mode)
              if (!catalogMode) return null
              return (
                <ModeCard
                  key={`${modeStatus.game_type}:${modeStatus.mode}`}
                  title={t(catalogMode.modeTitleKey)}
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
