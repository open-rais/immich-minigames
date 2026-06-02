'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

import {
  Alert,
  Button,
  Card,
  LoadingSpinner,
} from '@/components/ui';

import { apiClient } from '@/lib/api-client';

import { GameInfo } from '@/types/api';

export default function Games() {
  const [games, setGames] =
    useState<GameInfo[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  useEffect(() => {
    async function loadGames() {
      try {
        const data =
          await apiClient.getAvailableGames();

        setGames(data);

        setError(null);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to load games',
        );
      } finally {
        setLoading(false);
      }
    }

    loadGames();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-white py-12 dark:from-gray-900 dark:to-black">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="mb-2 text-3xl font-bold text-gray-900 dark:text-white">
              🎮 Select a Game
            </h1>

            <p className="text-gray-600 dark:text-gray-400">
              Choose a game to start
              playing with your photo
              library
            </p>
          </div>

          <Link href="/settings">
            <Button variant="secondary">
              Settings
            </Button>
          </Link>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <LoadingSpinner />
          </div>
        ) : error ? (
          <Alert variant="error">
            {error}
          </Alert>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {games.map((game) => (
              <Link
                key={game.slug}
                href={`/${game.slug.replaceAll(
                  '_',
                  '-',
                )}`}
              >
                <Card
                  clickable
                  className="flex h-full flex-col p-6"
                >
                  <h2 className="mb-2 text-xl font-bold text-gray-900 dark:text-white">
                    {game.name}
                  </h2>

                  <p className="mb-4 flex-1 text-gray-600 dark:text-gray-400">
                    {game.description}
                  </p>

                  {game.modes.length > 0 && (
                    <div className="mb-4">
                      <div className="mb-2 text-sm font-medium text-gray-500">
                        Modes
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {game.modes.map(
                          (mode) => (
                            <span
                              key={
                                mode.slug
                              }
                              className="rounded-full bg-blue-100 px-3 py-1 text-xs text-blue-700 dark:bg-blue-900 dark:text-blue-200"
                            >
                              {
                                mode.name
                              }
                            </span>
                          ),
                        )}
                      </div>
                    </div>
                  )}

                  <Button size="sm">
                    Play Now →
                  </Button>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
