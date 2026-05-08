'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import GameLayout from '@/components/GameLayout';
import { Button, Card, Alert, LoadingSpinner } from '@/components/ui';
import { apiClient } from '@/lib/api-client';
import { storage } from '@/lib/storage';
import { GameSession, RoundData, GameItem } from '@/types/api';

export default function MoreOrLessGame() {
  const router = useRouter();
  const [session, setSession] = useState<GameSession | null>(null);
  const [roundData, setRoundData] = useState<RoundData | null>(null);
  const [loading, setLoading] = useState(true);
  const [answering, setAnswering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedBack, setFeedback] = useState<{ correct: boolean; message: string } | null>(null);

  useEffect(() => {
    initializeGame();
  }, []);

  const initializeGame = async () => {
    try {
      setLoading(true);
      const newSession = await apiClient.createSession('more-or-less', 'person-items');
      setSession(newSession);
      storage.setCurrentSessionId(newSession.id);

      const initial = await apiClient.getNextRound(newSession.id);
      setRoundData(initial);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to initialize game';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleGuess = async (guess: 'more' | 'less') => {
    if (!session || !roundData) return;

    setAnswering(true);
    setFeedback(null);

    try {
      const result = await apiClient.submitGuess(session.id, {
        sessionId: session.id,
        guess,
      });

      const updatedSession = await apiClient.getSession(session.id);
      setSession(updatedSession);
      setFeedback({
        correct: result.correct,
        message: result.message,
      });

      setTimeout(async () => {
        const next = await apiClient.getNextRound(session.id);
        setRoundData(next);
        setFeedback(null);
      }, 2000);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to submit guess';
      setFeedback({
        correct: false,
        message: message,
      });
    } finally {
      setAnswering(false);
    }
  };

  const handleQuit = async () => {
    if (session) {
      try {
        await apiClient.completeSession(session.id);
      } catch {
        // Silently fail
      }
    }
    storage.clearCurrentSessionId();
    router.push('/games');
  };

  if (loading) {
    return (
      <GameLayout title="More or Less" showBackButton={false}>
        <div className="flex justify-center items-center min-h-[400px]">
          <LoadingSpinner />
        </div>
      </GameLayout>
    );
  }

  if (error || !session || !roundData) {
    return (
      <GameLayout title="More or Less">
        <div className="max-w-2xl mx-auto px-4 py-12">
          <Alert variant="error">Error loading game: {error}</Alert>
          <Button onClick={initializeGame} className="mt-4">
            Try Again
          </Button>
        </div>
      </GameLayout>
    );
  }

  return (
    <GameLayout title="More or Less">
      <div className="max-w-2xl mx-auto px-4 py-12">
        {/* Score Display */}
        <div className="mb-8 text-center">
          <div className="text-4xl font-bold text-blue-600 dark:text-blue-400">{session.score}</div>
          <div className="text-gray-600 dark:text-gray-400">Score</div>
          <div className="text-sm text-gray-500 dark:text-gray-500 mt-2">
            Round {session.roundsCompleted + 1}
          </div>
        </div>

        {/* Game Cards */}
        <div className="grid grid-cols-2 gap-6 mb-8">
          {/* Current Item */}
          <Card className="p-6 text-center">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">Current</div>
            <div className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              {roundData.current.count || roundData.current.name}
            </div>
            {roundData.current.type === 'person' && (
              <div className="text-gray-600 dark:text-gray-400">
                {roundData.current.name}
              </div>
            )}
          </Card>

          {/* Next Item (Hidden) */}
          <Card className="p-6 text-center bg-gray-100 dark:bg-gray-800">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">Next</div>
            <div className="text-3xl font-bold text-gray-300 dark:text-gray-600">?</div>
            <div className="text-gray-400 dark:text-gray-500 text-sm">Guess...</div>
          </Card>
        </div>

        {/* Feedback */}
        {feedBack && (
          <Alert variant={feedBack.correct ? 'success' : 'error'} className="mb-8">
            {feedBack.correct ? '✓' : '✗'} {feedBack.message}
          </Alert>
        )}

        {/* Controls */}
        <div className="flex gap-4 mb-8">
          <Button
            onClick={() => handleGuess('less')}
            disabled={answering}
            className="flex-1"
            size="lg"
          >
            {answering ? <LoadingSpinner size="sm" /> : '← Less'}
          </Button>
          <Button
            onClick={() => handleGuess('more')}
            disabled={answering}
            className="flex-1"
            size="lg"
          >
            {answering ? <LoadingSpinner size="sm" /> : 'More →'}
          </Button>
        </div>

        {/* Quit Button */}
        <div className="text-center">
          <Button onClick={handleQuit} variant="secondary">
            Quit Game
          </Button>
        </div>
      </div>
    </GameLayout>
  );
}
