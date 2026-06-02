export interface GameMode {
  slug: string;
  name: string;
  description: string;
}

export interface GameInfo {
  slug: string;
  name: string;
  description: string;
  modes: GameMode[];
}

export interface GameSession {
  session_id: string;
  game_slug: string;
  mode_slug: string;

  score: number;
  streak: number;
  rounds_played: number;

  is_active: boolean;
  is_game_over: boolean;

  round: PublicRound | null;
}

export interface PublicPerson {
  id: string;
  name: string;
  thumbnail_url: string | null;
  asset_count: number | null;
}

export interface PublicRound {
  left_person: PublicPerson;
  right_person: PublicPerson;
}

export interface SubmitAnswerResponse {
  correct: boolean;
  game_over: boolean;

  score: number;
  streak: number;

  correct_answer?: string;

  revealed: {
    name: string;
    asset_count: number;
  };

  next_round?: PublicRound;
}

export interface HealthResponse {
  status: 'ok' | 'error';
  database?: boolean;
  redis?: boolean;
  immichApi?: boolean;
}

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

export interface ApiErrorResponse {
  detail: string | Array<{ loc: string[]; msg: string; type: string }>;
}
