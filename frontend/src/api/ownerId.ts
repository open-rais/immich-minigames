const STORAGE_KEY = "minigames.ownerId"

/**
 * There's no real login yet (see docs/TODO/ROADMAP.md), so requests are attributed to a random
 * id generated once per browser and persisted in localStorage, reused as X-Owner-Id until real
 * auth exists.
 */
export function getOwnerId(): string {
  const existing = localStorage.getItem(STORAGE_KEY)
  if (existing) return existing

  const generated = crypto.randomUUID()
  localStorage.setItem(STORAGE_KEY, generated)
  return generated
}
