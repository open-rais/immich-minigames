const STORAGE_KEY = "minigames.ownerId"

/**
 * crypto.randomUUID() only exists in secure contexts (https, or http on localhost/127.0.0.1) -
 * accessing the dev server from another device over plain http://<lan-ip> (e.g. a phone) doesn't
 * qualify, so it's undefined there. This id is just an anonymous request tag, not
 * security-sensitive, so a Math.random()-based fallback is fine. See docs/TODO/DEV_NOTES.md.
 */
function generateId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === "x" ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/**
 * There's no real login yet (see docs/TODO/ROADMAP.md), so requests are attributed to a random
 * id generated once per browser and persisted in localStorage, reused as X-Owner-Id until real
 * auth exists.
 */
export function getOwnerId(): string {
  const existing = localStorage.getItem(STORAGE_KEY)
  if (existing) return existing

  const generated = generateId()
  localStorage.setItem(STORAGE_KEY, generated)
  return generated
}
