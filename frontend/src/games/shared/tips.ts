// QoL tips: the short hint that shows up on a finished game's screen (see GameScreens.tsx's
// FinishedScreen) pointing at a feature the player may not have found yet - reporting bad
// metadata, the leaderboards, replaying a game's rounds, the daily share message.
//
// It is deliberately *not* shown after every game: a hint that is always there stops being read.
// Each tip declares the context it makes sense in, so a mode with no rounds view never suggests
// "View game", and an already-installed PWA never suggests installing itself.

/** Chance that a finished game shows a tip at all. Rolled once per finished screen. */
export const TIP_CHANCE = 0.3

/** What the finished screen knows about itself, for deciding which tips apply. */
export interface TipContext {
  /** This mode has a rounds view registered (the "View game" button is on screen). */
  hasRoundsView: boolean
  /** This was a daily game (the "Share" button is on screen). */
  isDaily: boolean
  /** The app is running as a normal browser tab, i.e. it can still be installed. */
  canInstall: boolean
}

interface Tip {
  /** Suffix of the i18n key under `common.tips.` */
  key: string
  applies: (ctx: TipContext) => boolean
}

const ALWAYS = () => true

const TIPS: Tip[] = [
  { key: "report", applies: (c) => c.hasRoundsView },
  { key: "leaderboard", applies: ALWAYS },
  { key: "relive", applies: (c) => c.hasRoundsView },
  { key: "profileHistory", applies: ALWAYS },
  { key: "roundsImmich", applies: (c) => c.hasRoundsView },
  { key: "install", applies: (c) => c.canInstall },
  { key: "dailyShare", applies: (c) => c.isDaily },
]

/**
 * The full i18n key of the tip to show, or null for the (majority of) games that show none.
 * `random` is injected so tests can pin both rolls - the first decides whether a tip shows at
 * all, the second picks which one.
 */
export function pickTip(ctx: TipContext, random: () => number = Math.random): string | null {
  if (random() >= TIP_CHANCE) return null
  const candidates = TIPS.filter((tip) => tip.applies(ctx))
  if (candidates.length === 0) return null
  const index = Math.min(Math.floor(random() * candidates.length), candidates.length - 1)
  return `common.tips.${candidates[index].key}`
}

/**
 * False once the app is running from the home screen / as an installed app, in which case
 * suggesting the player install it would be nonsense. Guarded because `matchMedia` is missing in
 * non-browser environments (tests, SSR-style tooling).
 */
export function canInstallApp(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false
  if (window.matchMedia("(display-mode: standalone)").matches) return false
  // iOS Safari never implemented the display-mode media query for home-screen apps.
  return !(navigator as Navigator & { standalone?: boolean }).standalone
}
