import { apiClient } from "./client"
import type { AlbumSearchOut } from "./types/albums"
import type {
  CreateGameIn,
  CurrentGameOut,
  GameOut,
  PlayRoundIn,
  PlayRoundOut,
  RecentGamesOut,
} from "./types/common"
import type { LeaderboardOut, LeaderboardWindow } from "./types/leaderboard"
import type { PersonSearchOut } from "./types/persons"
import type { GameRecordsOut } from "./types/records"

export async function createGame(type: string, mode: string): Promise<GameOut> {
  const body: CreateGameIn = { type, mode }
  const { data } = await apiClient.post<GameOut>("/games", body)
  return data
}

export async function getGame(id: string): Promise<GameOut> {
  const { data } = await apiClient.get<GameOut>(`/games/${id}`)
  return data
}

// Idle-screen "Continuar" lookup - null when the logged-in account has no unfinished
// game for this (gameType, mode). See backend/src/api/api.py's get_current_game.
export async function getCurrentGame(gameType: string, mode: string): Promise<GameOut | null> {
  const { data } = await apiClient.get<CurrentGameOut>("/games/current", {
    params: { game_type: gameType, mode },
  })
  return data.game
}

// Profile "Ver juegos" modal - see api/api.py's get_recent_games.
export async function getRecentGames(): Promise<RecentGamesOut["games"]> {
  const { data } = await apiClient.get<RecentGamesOut>("/games/recent")
  return data.games
}

// Personal-best score per (game_type, mode) - shown in the main menu - see
// backend/src/api/api.py's get_game_records.
export async function getGameRecords(): Promise<GameRecordsOut> {
  const { data } = await apiClient.get<GameRecordsOut>("/games/records")
  return data
}

// Top-15 leaderboard for a (game_type, mode) - see backend/src/api/api.py's
// get_leaderboard.
export async function getLeaderboard(
  gameType: string,
  mode: string,
  window: LeaderboardWindow,
): Promise<LeaderboardOut> {
  const { data } = await apiClient.get<LeaderboardOut>(`/games/${gameType}/${mode}/leaderboard`, {
    params: { window },
  })
  return data
}

// One endpoint for every game's guess - which body shape is valid is fixed by the game's type/mode
// server-side (see backend/src/api/dto/common.py's parse_guess), so callers just pass the body for
// their game. Replaces the former per-game playRound/playGeoguessrRound/playDateguessrRound trio.
export async function playRound(
  gameId: string,
  roundId: string,
  body: PlayRoundIn,
): Promise<PlayRoundOut> {
  const { data } = await apiClient.post<PlayRoundOut>(`/games/${gameId}/rounds/${roundId}`, body)
  return data
}

// Word-prefix match on named people's full name - see backend/src/services/immich_service.py's
// search_persons. Small pages by default (matches the backend's own default limit=3).
export async function searchPersons(
  query: string,
  opts?: { offset?: number; limit?: number },
): Promise<PersonSearchOut> {
  const { data } = await apiClient.get<PersonSearchOut>("/persons/search", {
    params: { query, offset: opts?.offset, limit: opts?.limit },
  })
  return data
}

// Word-prefix match on album names - see backend/src/services/immich/albums.py's search_albums.
// Albumdle's guess-input autocomplete (roadmap #14) - mirrors searchPersons above exactly.
export async function searchAlbums(
  query: string,
  opts?: { offset?: number; limit?: number },
): Promise<AlbumSearchOut> {
  const { data } = await apiClient.get<AlbumSearchOut>("/albums/search", {
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

// An album has no thumbnail of its own - the backend resolves its cover asset and proxies that
// asset's thumbnail (see backend/src/api/api.py's album thumbnail route). Used by MoreOrLess's
// albumAssets mode.
export function albumThumbnailUrl(albumId: string): string {
  return `/api/v1/albums/${albumId}/thumbnail`
}
