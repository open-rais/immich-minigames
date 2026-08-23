import { useMemo } from "react"

import { getDailyStatus } from "../api/daily"
import { useLiveQuery } from "../api/queryCache"
import type { DailyStatusOut } from "../api/types/daily"
import type { CatalogGame } from "../games/catalog"
import { GAME_CATALOG } from "../games/catalog"
import { DAILY_STATUS_KEY } from "../games/shared/useGameSession"

// Shared navigation model behind the [‹] game [›] / [‹] mode [›] rows on both leaderboard pages
// (menu/LeaderboardPage.tsx and menu/DailyLeaderboardPage.tsx).
//
// Two independent rings: the outer one walks categories (the "daily" pseudo-category first, then
// every game in menu order), the inner one walks that category's own modes. Both wrap around, so
// no arrow is ever a dead end, and crossing categories always lands on the destination's first
// mode.

// Not a real gameType - the id the daily leaderboards share as their category, the same way
// menu/DailySection.tsx uses a fixed "daily" section id rather than a game's own.
export const DAILY_CATEGORY = "daily"

export interface LeaderboardTarget {
  gameType: string
  mode: string
}

export interface LeaderboardCategory {
  id: string
  // i18n key, not a rendered string - the caller has `t` in scope, this module doesn't.
  titleKey: string
  targets: LeaderboardTarget[]
}

export function sameTarget(a: LeaderboardTarget, b: LeaderboardTarget): boolean {
  return a.gameType === b.gameType && a.mode === b.mode
}

// Steps `index` by `delta` around a ring of `length` items. Negative deltas wrap backwards.
export function cycleIndex(length: number, index: number, delta: number): number {
  if (length <= 0) return 0
  return (((index + delta) % length) + length) % length
}

// The daily rotation is admin-configurable at runtime, so a mode can be disabled while someone is
// still looking at (or deep-linking to) its board. Keeping the current target in the ring means
// that page still knows where it sits and stays navigable, instead of collapsing to index -1.
export function withCurrentTarget(
  targets: LeaderboardTarget[],
  current: LeaderboardTarget,
): LeaderboardTarget[] {
  return targets.some((t) => sameTarget(t, current)) ? targets : [...targets, current]
}

export function buildCategories(
  dailyTargets: LeaderboardTarget[],
  catalog: CatalogGame[] = GAME_CATALOG,
): LeaderboardCategory[] {
  const categories: LeaderboardCategory[] = []
  // Omitted entirely when no mode is in the rotation - same call the main menu's DailySection
  // makes when it renders nothing at all rather than an empty section.
  if (dailyTargets.length > 0) {
    categories.push({ id: DAILY_CATEGORY, titleKey: "daily.title", targets: dailyTargets })
  }
  for (const game of catalog) {
    categories.push({
      id: game.gameType,
      titleKey: game.gameTitleKey,
      targets: game.modes.map((m) => ({ gameType: game.gameType, mode: m.mode })),
    })
  }
  return categories
}

export function leaderboardHref(
  categoryId: string,
  target: LeaderboardTarget,
  // Only ever applied to daily hrefs (that's the only board with a `?date=`); a normal leaderboard
  // has nothing to carry across.
  dailySearch = "",
): string {
  return categoryId === DAILY_CATEGORY
    ? `/daily/${target.gameType}/${target.mode}/leaderboard${dailySearch}`
    : `/${target.gameType}/${target.mode}/leaderboard`
}

export interface LeaderboardNav {
  category: LeaderboardCategory
  // The mode row's own label needs the game title too when the category is "daily", since there
  // one "mode" is really a (game, mode) pair from a different game each time.
  showGameInModeLabel: boolean
  prevCategoryHref: string
  nextCategoryHref: string
  prevModeHref: string
  nextModeHref: string
}

export function resolveNav(
  categories: LeaderboardCategory[],
  categoryId: string,
  current: LeaderboardTarget,
  dailySearch: string,
): LeaderboardNav | null {
  const categoryIndex = categories.findIndex((c) => c.id === categoryId)
  if (categoryIndex < 0) return null
  const category = categories[categoryIndex]
  const modeIndex = category.targets.findIndex((t) => sameTarget(t, current))
  if (modeIndex < 0) return null

  const categoryAt = (delta: number) => {
    const next = categories[cycleIndex(categories.length, categoryIndex, delta)]
    // Crossing categories always lands on the destination's first mode.
    return leaderboardHref(next.id, next.targets[0], next.id === DAILY_CATEGORY ? dailySearch : "")
  }
  const modeAt = (delta: number) =>
    leaderboardHref(
      category.id,
      category.targets[cycleIndex(category.targets.length, modeIndex, delta)],
      dailySearch,
    )

  return {
    category,
    showGameInModeLabel: category.id === DAILY_CATEGORY,
    prevCategoryHref: categoryAt(-1),
    nextCategoryHref: categoryAt(1),
    prevModeHref: modeAt(-1),
    nextModeHref: modeAt(1),
  }
}

// Both leaderboard pages fetch the daily status, not just the daily one: the category ring spans
// every board, so even a normal leaderboard needs to know whether "Daily" is in the rotation and
// which mode it would open. It's the same cached key the menu and useGameSession already use, so
// arriving here from either costs no extra request.
// Takes gameType/mode as plain strings rather than a LeaderboardTarget so the memo below has
// stable dependencies - an object literal built by the caller would be a new identity every render.
export function useLeaderboardNav(
  categoryId: string,
  gameType: string,
  mode: string,
  dailySearch = "",
): LeaderboardNav | null {
  const { state } = useLiveQuery<DailyStatusOut>(DAILY_STATUS_KEY, getDailyStatus)
  const dailyStatus = state.status === "loading" ? undefined : state.value

  return useMemo(() => {
    const current = { gameType, mode }
    let dailyTargets: LeaderboardTarget[] = (dailyStatus?.modes ?? []).map((m) => ({
      gameType: m.game_type,
      mode: m.mode,
    }))
    if (categoryId === DAILY_CATEGORY) dailyTargets = withCurrentTarget(dailyTargets, current)
    return resolveNav(buildCategories(dailyTargets), categoryId, current, dailySearch)
  }, [dailyStatus, categoryId, gameType, mode, dailySearch])
}
