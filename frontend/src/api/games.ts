import { apiClient } from "./client"
import type { CreateGameIn, GameOut, Guess, MoreOrLessPlayRoundIn, GeoguessrPlayRoundIn, PlayRoundOut } from "./types"

export async function createGame(type: string, mode: string): Promise<GameOut> {
  const body: CreateGameIn = { type, mode }
  const { data } = await apiClient.post<GameOut>("/games", body)
  return data
}

export async function getGame(id: string): Promise<GameOut> {
  const { data } = await apiClient.get<GameOut>(`/games/${id}`)
  return data
}

export async function playRound(gameId: string, roundId: string, guess: Guess): Promise<PlayRoundOut> {
  const body: MoreOrLessPlayRoundIn = { guess }
  const { data } = await apiClient.post<PlayRoundOut>(`/games/${gameId}/rounds/${roundId}`, body)
  return data
}

export async function playGeoguessrRound(
  gameId: string,
  roundId: string,
  latitude: number,
  longitude: number,
): Promise<PlayRoundOut> {
  const body: GeoguessrPlayRoundIn = { latitude, longitude }
  const { data } = await apiClient.post<PlayRoundOut>(`/games/${gameId}/rounds/${roundId}`, body)
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
