import axios, { AxiosError, AxiosInstance } from 'axios';
import {
  ImmichSettings,
  GameSession,
  GameStats,
  GameInfo,
  RoundData,
  RoundGuessRequest,
  RoundGuessResponse,
  HealthResponse,
  ApiErrorResponse,
} from '@/types/api';

class ApiClient {
  private client: AxiosInstance;
  private baseURL: string;

  constructor(baseURL: string = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') {
    this.baseURL = baseURL;
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // ============== Settings ==============
  async getSettings(): Promise<ImmichSettings> {
    try {
      const response = await this.client.get<ImmichSettings>('/api/settings');
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async updateSettings(settings: ImmichSettings): Promise<ImmichSettings> {
    try {
      const response = await this.client.post<ImmichSettings>('/api/settings', settings);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async testImmichConnection(url: string, apiKey: string): Promise<boolean> {
    try {
      await this.client.post('/api/settings/test', { immichUrl: url, apiKey });
      return true;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // ============== Games ==============
  async getAvailableGames(): Promise<GameInfo[]> {
    try {
      const response = await this.client.get<GameInfo[]>('/api/games');
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // ============== Sessions ==============
  async createSession(gameType: string, gameMode?: string): Promise<GameSession> {
    try {
      const response = await this.client.post<GameSession>('/api/sessions', {
        gameType,
        gameMode,
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async getSession(sessionId: string): Promise<GameSession> {
    try {
      const response = await this.client.get<GameSession>(`/api/sessions/${sessionId}`);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async completeSession(sessionId: string): Promise<GameSession> {
    try {
      const response = await this.client.post<GameSession>(
        `/api/sessions/${sessionId}/complete`
      );
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // ============== Rounds ==============
  async getNextRound(sessionId: string): Promise<RoundData> {
    try {
      const response = await this.client.get<RoundData>(`/api/rounds/${sessionId}/next`);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async submitGuess(sessionId: string, request: RoundGuessRequest): Promise<RoundGuessResponse> {
    try {
      const response = await this.client.post<RoundGuessResponse>(
        `/api/rounds/${sessionId}/guess`,
        request
      );
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // ============== Stats ==============
  async getGameStats(gameType?: string): Promise<GameStats[]> {
    try {
      const params = gameType ? { gameType } : {};
      const response = await this.client.get<GameStats[]>('/api/stats', { params });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async getSessionStats(sessionId: string): Promise<GameStats> {
    try {
      const response = await this.client.get<GameStats>(`/api/stats/${sessionId}`);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // ============== Health ==============
  async checkHealth(): Promise<HealthResponse> {
    try {
      const response = await this.client.get<HealthResponse>('/api/health');
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  // ============== Error Handling ==============
  private handleError(error: unknown): Error {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError<ApiErrorResponse>;
      const message =
        typeof axiosError.response?.data?.detail === 'string'
          ? axiosError.response.data.detail
          : axiosError.message;

      const err = new Error(message);
      (err as any).status = axiosError.response?.status;
      (err as any).data = axiosError.response?.data;
      return err;
    }
    return error instanceof Error ? error : new Error(String(error));
  }
}

export const apiClient = new ApiClient();
export default ApiClient;
