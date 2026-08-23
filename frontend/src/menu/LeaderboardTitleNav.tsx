import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { CycleNav } from "../games/shared/CycleNav"
import { GameModeSubtitle } from "../games/shared/GameModeSubtitle"
import type { LeaderboardNav } from "./leaderboardNav"

// The two [‹] … [›] rows under the "Leaderboard" heading, shared by menu/LeaderboardPage.tsx and
// menu/DailyLeaderboardPage.tsx: the top one walks game categories ("Daily" plus every game), the
// bottom one walks that category's modes. Both wrap around - see menu/leaderboardNav.ts.
//
// Navigations `replace` instead of pushing: cycling isn't a trail worth walking back through, and
// the page's own BackButton (which targets whatever board is on screen now) is the way out.
export function LeaderboardTitleNav({
  nav,
  gameTitle,
  modeTitle,
}: {
  // Null only while the category ring can't place the current board - render the static
  // "<game> · <mode>" subtitle then, exactly what this header showed before the arrows existed.
  nav: LeaderboardNav | null
  gameTitle: string
  modeTitle: string
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  if (!nav) return <GameModeSubtitle gameTitle={gameTitle} modeTitle={modeTitle} />

  const go = (href: string) => navigate(href, { replace: true })

  return (
    <div className="mt-2 flex flex-col gap-0.5">
      <CycleNav
        prevLabel={t("leaderboard.nav.previousGame")}
        nextLabel={t("leaderboard.nav.nextGame")}
        onPrev={() => go(nav.prevCategoryHref)}
        onNext={() => go(nav.nextCategoryHref)}
      >
        <h2 className="truncate text-xl font-bold text-ink">{t(nav.category.titleKey)}</h2>
      </CycleNav>
      <CycleNav
        prevLabel={t("leaderboard.nav.previousMode")}
        nextLabel={t("leaderboard.nav.nextMode")}
        onPrev={() => go(nav.prevModeHref)}
        onNext={() => go(nav.nextModeHref)}
      >
        {/* In the "daily" category each entry belongs to a different game, so the mode row has to
            name it; inside a single game's category the row above already did. */}
        {nav.showGameInModeLabel ? (
          <GameModeSubtitle gameTitle={gameTitle} modeTitle={modeTitle} />
        ) : (
          <h3 className="mt-1 truncate text-lg font-semibold text-muted">{modeTitle}</h3>
        )}
      </CycleNav>
    </div>
  )
}
