/**
 * Local Storage utilities
 * Manages client-side storage for sessions and UI state
 */

const STORAGE_KEYS = {
  CURRENT_SESSION_ID: 'immich-minigames:current-session',
  SETTINGS_CONFIGURED: 'immich-minigames:settings-configured',
  USER_PREFERENCES: 'immich-minigames:preferences',
};

export const storage = {
  // Session Management
  setCurrentSessionId(sessionId: string): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEYS.CURRENT_SESSION_ID, sessionId);
    }
  },

  getCurrentSessionId(): string | null {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(STORAGE_KEYS.CURRENT_SESSION_ID);
    }
    return null;
  },

  clearCurrentSessionId(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(STORAGE_KEYS.CURRENT_SESSION_ID);
    }
  },

  // Settings Configuration
  setSettingsConfigured(configured: boolean): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEYS.SETTINGS_CONFIGURED, String(configured));
    }
  },

  isSettingsConfigured(): boolean {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(STORAGE_KEYS.SETTINGS_CONFIGURED) === 'true';
    }
    return false;
  },

  // User Preferences
  setPreferences(preferences: Record<string, unknown>): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEYS.USER_PREFERENCES, JSON.stringify(preferences));
    }
  },

  getPreferences(): Record<string, unknown> {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(STORAGE_KEYS.USER_PREFERENCES);
      return stored ? JSON.parse(stored) : {};
    }
    return {};
  },

  // General utilities
  clear(): void {
    if (typeof window !== 'undefined') {
      Object.values(STORAGE_KEYS).forEach(key => localStorage.removeItem(key));
    }
  },
};

export default storage;
