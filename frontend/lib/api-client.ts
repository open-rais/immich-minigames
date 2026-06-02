import axios, { AxiosError, AxiosInstance } from 'axios';
import {
  GameSession,
  GameInfo,
  PublicRound,
  SubmitAnswerResponse,
  HealthResponse,
  ApiErrorResponse,
  ImmichSettings,
} from '@/types/api';

class ApiClient {
  private client: AxiosInstance;

  constructor(
    baseURL: string =
      process.env.NEXT_PUBLIC_API_URL ||
      'http://localhost:8000',
  ) {
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // SETTINGS
  async getSettings(): Promise<ImmichSettings> {
    const res = await this.client.get('/api/settings');
    return res.data;
  }

  async updateSettings(data: ImmichSettings): Promise<ImmichSettings> {
    const res = await this.client.post('/api/settings', data);
    return res.data;
  }

  async testImmichConnection(immichUrl: string, apiKey: string): Promise<void> {
    await this.client.post('/api/settings/test', {
      immichUrl,
      apiKey,
    });
  }

  // ============== Games ==============
  async getAvailableGames(): Promise<GameInfo[]> {
    const res = await this.client.get('/api/games');
    return res.data;
  }

  // ============== Sessions ==============
  async createSession(
    game_slug: string,
    mode_slug: string,
  ): Promise<GameSession> {
    const res = await this.client.post(
      '/api/sessions',
      {
        game_slug,
        mode_slug,
      },
    );
    return res.data;
  }

  async getSession(
    session_id: string,
  ): Promise<GameSession> {
    const res = await this.client.get(
      `/api/sessions/${session_id}`,
    );
    return res.data;
  }

  async endSession(
    session_id: string,
  ): Promise<void> {
    await this.client.delete(
      `/api/sessions/${session_id}`,
    );
  }

  async submitAnswer(
    session_id: string,
    answer: 'more' | 'less',
  ): Promise<SubmitAnswerResponse> {
    const res = await this.client.post(
      `/api/sessions/${session_id}/answer`,
      { answer },
    );
    return res.data;
  }

  // ============== Health ==============
  async checkHealth(): Promise<HealthResponse> {
    const res = await this.client.get('/api/health');
    return res.data;
  }

  // ERROR
  private handleError(error: unknown): Error {
    if (axios.isAxiosError(error)) {
      const err = new Error(
        (error.response?.data as ApiErrorResponse)?.detail?.toString() ||
          error.message,
      );
      return err;
    }
    return new Error(String(error));
  }
}

export const apiClient = new ApiClient();
