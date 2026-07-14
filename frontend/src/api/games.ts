import { apiClient } from "./client"
import type { CreateGameIn, GameOut, PersonSearchOut, PlayRoundIn, PlayRoundOut } from "./types"

export async function createGame(type: string, mode: string): Promise<GameOut> {
  const body: CreateGameIn = { type, mode }
  const { data } = await apiClient.post<GameOut>("/games", body)
  return data
}

export async function getGame(id: string): Promise<GameOut> {
  const { data } = await apiClient.get<GameOut>(`/games/${id}`)
  return data
}

// One endpoint for every game's guess - which body shape is valid is fixed by the game's type/mode
// server-side (see backend/src/api/schemas.py's parse_guess), so callers just pass the body for
// their game. Replaces the former per-game playRound/playGeoguessrRound/playDateguessrRound trio.
export async function playRound(gameId: string, roundId: string, body: PlayRoundIn): Promise<PlayRoundOut> {
  const { data } = await apiClient.post<PlayRoundOut>(`/games/${gameId}/rounds/${roundId}`, body)
  return data
}

// Word-prefix match on named people's full name - see backend/src/services/immich_service.py's
// search_persons. Small pages by default (matches the backend's own default limit=3).
export async function searchPersons(query: string, opts?: { offset?: number; limit?: number }): Promise<PersonSearchOut> {
  const { data } = await apiClient.get<PersonSearchOut>("/persons/search", {
    params: { query, offset: opts?.offset, limit: opts?.limit },
  })
  return data
}

// Relative path - same-origin in prod, proxied by Vite in dev (see vite.config.ts) - the backend
// proxies these bytes from Immich's own REST API (see docs/ARCHITECTURE/IMMICH.md).
export function personThumbnailUrl(personId: string): string {
  return `/api/v1/people/${personId}/thumbnail`
}

export function assetThumbnailUrl(assetId: string): string {
  return `/api/v1/assets/${assetId}/thumbnail`
}
