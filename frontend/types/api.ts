/**
 * API Types for immich-minigames
 * Communication contracts with the backend
 */

// Settings
export interface ImmichSettings {
  immichUrl: string;
  apiKey: string;
  id?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface SettingsResponse {
  immichUrl: string;
  apiKey: string;
}

// Session
export interface GameSession {
  id: string;
  gameType: string;
  status: 'active' | 'completed' | 'abandoned';
  score: number;
  roundsCompleted: number;
  startedAt: string;
  completedAt?: string;
  gameData?: Record<string, unknown>;
}

export interface CreateSessionRequest {
  gameType: string;
  gameMode?: string;
}

// Game Stats
export interface GameStats {
  id: string;
  sessionId: string;
  gameType: string;
  score: number;
  roundsCompleted: number;
  accuracy?: number;
  playedAt: string;
  duration?: number;
}

export interface GameStatsResponse {
  data: GameStats[];
  total: number;
  average: number;
}

// Game Data
export interface GameItem {
  id: string;
  type: 'person' | 'album' | 'photo';
  name?: string;
  count?: number;
  photoId?: string;
  photoUrl?: string;
  exifDate?: string;
}

export interface RoundData {
  current: GameItem;
  next: GameItem;
  roundNumber: number;
  totalRounds?: number;
}

export interface RoundResponse {
  roundData: RoundData;
  sessionId: string;
}

export interface RoundGuessRequest {
  sessionId: string;
  guess: 'more' | 'less' | 'equal';
  metadata?: Record<string, unknown>;
}

export interface RoundGuessResponse {
  correct: boolean;
  actual: number;
  currentValue: number;
  score: number;
  message: string;
}

// Games
export interface GameInfo {
  id: string;
  name: string;
  description: string;
  modes?: string[];
  status: 'available' | 'coming-soon' | 'disabled';
}

export interface GamesListResponse {
  games: GameInfo[];
}

// Health
export interface HealthResponse {
  status: 'ok' | 'error';
  database?: boolean;
  redis?: boolean;
  immichApi?: boolean;
}

// Error Response
export interface ApiErrorResponse {
  detail: string | Array<{ loc: string[]; msg: string; type: string }>;
}
