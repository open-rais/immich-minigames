// Its own module (rather than living in ValueBadge.tsx) so MoreOrLessRounds.tsx can import it too
// without pulling in a component - same Fast-Refresh-friendly split modeConfig.ts already uses
// (oxlint's react/only-export-components).

// A plain calendar date has no time component - `new Date("YYYY-MM-DD")` parses that as UTC
// midnight, so formatting must stay in UTC too or it silently shifts a day backward in any
// timezone behind UTC. Same UTC-safe pattern games/Immichdle/ClueCell.tsx already uses for its own
// date clue, and games/Dateguessr/timeMath.ts's day-index math guards the same pitfall.
export function formatBirthDate(value: string, language: string): string {
  return new Intl.DateTimeFormat(language, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(value))
}
