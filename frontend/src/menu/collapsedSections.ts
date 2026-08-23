// Persists which menu sections (a game's own gameType, or the literal "daily") are collapsed -
// per browser/device, not per account, same scope as theme/ThemeProvider.tsx's STORAGE_KEY and
// i18n/index.ts's own. Stores the *collapsed* ids, not the expanded ones: a game added to the
// catalog later is simply never in this list, so it starts out expanded with no migration needed.
//
// Wrapped in try/catch (unlike ThemeProvider/i18n's own localStorage reads) - a private-browsing
// tab or blocked storage makes localStorage throw rather than just return null, and the safe
// fallback here is "nothing is collapsed", not a broken menu.

const STORAGE_KEY = "minigames-collapsed-sections"

function readCollapsedIds(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string") : []
  } catch {
    return []
  }
}

function writeCollapsedIds(ids: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
  } catch {
    // Private browsing / blocked storage - the toggle still works for this render, it just won't
    // survive a reload. Same "best effort, never throw" convention as the rest of this module.
  }
}

export function isCollapsed(id: string): boolean {
  return readCollapsedIds().includes(id)
}

export function setCollapsed(id: string, value: boolean): void {
  const current = readCollapsedIds()
  const next = value ? [...current.filter((existing) => existing !== id), id] : current.filter((existing) => existing !== id)
  writeCollapsedIds(next)
}
