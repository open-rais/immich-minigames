'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Card, Button, LoadingSpinner, Alert } from '@/components/ui';
import { apiClient } from '@/lib/api-client';
import { GameInfo } from '@/types/api';

export default function Games() {
  const [games, setGames] = useState<GameInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadGames() {
      try {
        const data = await apiClient.getAvailableGames();
        setGames(data);
        setError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load games';
        setError(message);
      } finally {
        setLoading(false);
      }
    }

    loadGames();
  }, []);

  const availableGames = games.filter(g => g.status === 'available');
  const comingSoon = games.filter(g => g.status === 'coming-soon');

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-white dark:from-gray-900 dark:to-black py-12">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              🎮 Select a Game
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              Choose a game to start playing with your photo library
            </p>
          </div>
          <Link href="/settings">
            <Button variant="secondary">Settings</Button>
          </Link>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <LoadingSpinner />
          </div>
        ) : error ? (
          <Alert variant="error">{error}</Alert>
        ) : (
          <>
            {/* Available Games */}
            {availableGames.length > 0 && (
              <div className="mb-12">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
                  Available Games
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {availableGames.map(game => (
                    <Link key={game.id} href={`/${game.id}`}>
                      <Card clickable className="p-6 h-full flex flex-col">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                          {game.name}
                        </h3>
                        <p className="text-gray-600 dark:text-gray-400 mb-4 flex-1">
                          {game.description}
                        </p>
                        {game.modes && game.modes.length > 0 && (
                          <div className="text-sm text-gray-500 dark:text-gray-500 mb-4">
                            Modes: {game.modes.join(', ')}
                          </div>
                        )}
                        <Button variant="primary" size="sm">
                          Play Now →
                        </Button>
                      </Card>
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Coming Soon */}
            {comingSoon.length > 0 && (
              <div>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
                  Coming Soon
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {comingSoon.map(game => (
                    <Card key={game.id} className="p-6 opacity-60">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                        {game.name}
                      </h3>
                      <p className="text-gray-600 dark:text-gray-400 mb-4">{game.description}</p>
                      <Button variant="secondary" size="sm" disabled>
                        Coming Soon
                      </Button>
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
