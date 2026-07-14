// A "day index" is a whole number of days since the Unix epoch, computed purely from a calendar
// date's (year, month, day) components via Date.UTC - it never carries real timezone/instant
// meaning, it's just an integer arithmetic trick to keep every conversion in this file consistent
// with itself. That sidesteps the classic Date.toISOString()-through-UTC pitfall (a local calendar
// day silently shifting by one near a timezone boundary): as long as every read/write here goes
// through dayIndexOf/dateFromDayIndex, "day 19000" always means the same calendar day everywhere.
const MS_PER_DAY = 86_400_000

export function dayIndexOf(year: number, monthIndex: number, day: number): number {
  return Math.round(Date.UTC(year, monthIndex, day) / MS_PER_DAY)
}

export function dateFromDayIndex(dayIndex: number): Date {
  return new Date(dayIndex * MS_PER_DAY)
}

export function isoFromDayIndex(dayIndex: number): string {
  const d = dateFromDayIndex(dayIndex)
  const y = String(d.getUTCFullYear()).padStart(4, "0")
  const m = String(d.getUTCMonth() + 1).padStart(2, "0")
  const day = String(d.getUTCDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}

export function dayIndexFromIso(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number)
  return dayIndexOf(y, m - 1, d)
}

// Local "today" - the one place this file looks at the real current instant/timezone, to know
// what calendar day the player is actually experiencing right now.
export function todayDayIndex(): number {
  const now = new Date()
  return dayIndexOf(now.getFullYear(), now.getMonth(), now.getDate())
}
