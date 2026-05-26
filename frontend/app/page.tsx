'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Button, Alert, LoadingSpinner } from '@/components/ui';
import { apiClient } from '@/lib/api-client';
import { storage } from '@/lib/storage';
import { HealthResponse } from '@/types/api';

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function checkHealth() {
      try {
        const result = await apiClient.checkHealth();
        setHealth(result);

        if (result.status === 'ok') {
          setError(null);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to connect to backend';
        setError(message);
      } finally {
        setLoading(false);
      }
    }

    checkHealth();
  }, []);

  const isSettingsConfigured = storage.isSettingsConfigured();

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-black dark:to-gray-900">
      {/* Hero Section */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
        <div className="text-center">
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-4">
            🎮 Immich Minigames
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-300 mb-8 max-w-2xl mx-auto">
            Transform your self-hosted photo library into interactive minigames. Play solo, track
            your scores, and have fun with your memories.
          </p>

          {/* Status Indicator */}
          <div className="mb-12">
            {loading ? (
              <div className="flex justify-center">
                <LoadingSpinner size="sm" />
              </div>
            ) : error ? (
              <Alert variant="error" className="inline-block">
                <strong>Backend Connection Error:</strong> {error}
              </Alert>
            ) : health?.status === 'ok' ? (
              <Alert variant="success" className="inline-block">
                ✓ Backend is running and ready!
              </Alert>
            ) : null}
          </div>

          {/* Navigation */}
          <div className="flex gap-4 justify-center flex-wrap">
            {isSettingsConfigured ? (
              <>
                <Link href="/games">
                  <Button size="lg">Play Games →</Button>
                </Link>
                <Link href="/settings">
                  <Button variant="secondary" size="lg">
                    Settings
                  </Button>
                </Link>
              </>
            ) : (
              <>
                <Link href="/settings">
                  <Button size="lg">Configure Immich Connection →</Button>
                </Link>
              </>
            )}
          </div>
        </div>

        {/* Features */}
        <div className="mt-20 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
          {[
            { title: '🎯 More or Less', description: 'Guess if the next item has more or less' },
            {
              title: '🌍 Geoguessr',
              description: 'Place photos on a map based on metadata',
            },
            {
              title: '📅 Dateguessr',
              description: 'Timeline dating game using photo timestamps',
            },
            {
              title: '🔍 Who Is There',
              description: 'Identify people hidden in photos',
            },
            {
              title: '🎪 Immichdle',
              description: 'Guess a person using hints',
            },
            {
              title: '🏆 High Scores',
              description: 'Track and compete with your own records',
            },
          ].map((feature, i) => (
            <div
              key={i}
              className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700"
            >
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                {feature.title}
              </h3>
              <p className="text-gray-600 dark:text-gray-400">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
