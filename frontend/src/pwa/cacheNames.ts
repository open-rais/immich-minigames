// Shared between src/sw.ts (which populates this cache) and the logout flow (which clears it) -
// a literal string duplicated in both places would drift silently instead of breaking loudly.
export const API_CACHE_NAME = "minigames-api-v1"
