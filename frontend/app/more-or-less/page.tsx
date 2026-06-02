'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import GameLayout from '@/components/GameLayout';
import { Alert, Button, Card, LoadingSpinner } from '@/components/ui';

import { apiClient } from '@/lib/api-client';
import { storage } from '@/lib/storage';

import { GameSession, PublicRound, SubmitAnswerResponse } from '@/types/api';

type Phase = 'idle' | 'counting' | 'result' | 'sliding' | 'border-fading';

export default function MoreOrLessGame() {
  const router = useRouter();

  const [session, setSession] = useState<GameSession | null>(null);
  const [round, setRound] = useState<PublicRound | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [phase, setPhase] = useState<Phase>('idle');
  const [displayedCount, setDisplayedCount] = useState(0);
  const [apiResult, setApiResult] = useState<SubmitAnswerResponse | null>(null);
  const [pendingRound, setPendingRound] = useState<PublicRound | null>(null);
  const [isDesktop, setIsDesktop] = useState(true);

  const rafRef = useRef<number | null>(null);
  const rightWrapperRef = useRef<HTMLDivElement>(null);
  const pendingRoundRef = useRef<PublicRound | null>(null);
  const borderFadeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  pendingRoundRef.current = pendingRound;

  useEffect(() => {
    const check = () => setIsDesktop(window.innerWidth >= 768);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  useEffect(() => {
    initializeGame();
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (borderFadeTimerRef.current) clearTimeout(borderFadeTimerRef.current);
    };
  }, []);

  const initializeGame = async () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    if (borderFadeTimerRef.current) clearTimeout(borderFadeTimerRef.current);
    if (rightWrapperRef.current) {
      rightWrapperRef.current.style.transition = '';
      rightWrapperRef.current.style.transform = '';
    }
    setPhase('idle');
    setDisplayedCount(0);
    setApiResult(null);
    setPendingRound(null);
    setError(null);

    try {
      setLoading(true);
      const created = await apiClient.createSession('more_or_less', 'person-items');
      setSession(created);
      storage.setCurrentSessionId(created.session_id);
      setRound(created.round);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initialize game');
    } finally {
      setLoading(false);
    }
  };

  const handleGuess = async (answer: 'more' | 'less') => {
    if (!session || phase !== 'idle') return;

    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    setPhase('counting');
    setDisplayedCount(0);
    setApiResult(null);

    let result: SubmitAnswerResponse;
    try {
      result = await apiClient.submitAnswer(session.session_id, answer);
    } catch (err) {
      setPhase('idle');
      setError(err instanceof Error ? err.message : 'Failed to submit answer');
      return;
    }

    setApiResult(result);

    if (result.game_over) {
      setSession((prev) =>
        prev
          ? {
              ...prev,
              score: result.score,
              streak: result.streak,
              is_active: false,
              is_game_over: true,
            }
          : prev,
      );
    } else {
      setPendingRound(result.next_round ?? null);
      apiClient.getSession(session.session_id).then(setSession).catch(() => {});
    }

    // Animate count 0 → target with ease-out cubic
    const target = result.revealed.asset_count;
    const duration = 1200;
    const startTime = Date.now();

    const tick = () => {
      const progress = Math.min((Date.now() - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayedCount(Math.round(eased * target));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setDisplayedCount(target);
        setPhase('result');
      }
    };

    rafRef.current = requestAnimationFrame(tick);
  };

  // result → sliding (only when game continues)
  useEffect(() => {
    if (phase !== 'result' || !apiResult || apiResult.game_over) return;
    const t = setTimeout(() => setPhase('sliding'), 1500);
    return () => clearTimeout(t);
  }, [phase, apiResult]);

  // Slide animation using direct DOM manipulation to avoid React transition conflicts
  useEffect(() => {
    if (phase !== 'sliding' || !rightWrapperRef.current) return;

    const el = rightWrapperRef.current;
    const slideTransform = isDesktop
      ? 'translateX(calc(-100% - 1.5rem))'
      : 'translateY(calc(-100% - 1.5rem))';

    // Set transition first, then apply transform on the next frame so the
    // browser registers the "from" state before animating
    // Slow, pronounced ease-in-out: fast acceleration + fast deceleration
    el.style.transition = 'transform 0.85s cubic-bezier(0.65, 0, 0.35, 1)';
    const rafId = requestAnimationFrame(() => {
      el.style.transform = slideTransform;
    });

    const handleEnd = (e: TransitionEvent) => {
      if (e.propertyName !== 'transform') return;
      el.removeEventListener('transitionend', handleEnd);

      // Card is now at the left position — show the ring fading out
      setPhase('border-fading');

      // After the ring fade animation (0.75s), do the content swap
      borderFadeTimerRef.current = setTimeout(() => {
        const next = pendingRoundRef.current;
        if (next) setRound(next);
        setPendingRound(null);
        setPhase('idle');
        setApiResult(null);
        setDisplayedCount(0);
        el.style.transition = '';
        el.style.transform = '';
      }, 780);
    };

    el.addEventListener('transitionend', handleEnd);
    return () => {
      cancelAnimationFrame(rafId);
      el.removeEventListener('transitionend', handleEnd);
    };
  }, [phase, isDesktop]);

  const handleQuit = async () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    if (session) {
      try {
        await apiClient.endSession(session.session_id);
      } catch {}
    }
    storage.clearCurrentSessionId();
    router.push('/games');
  };

  // --- Derived display values ---
  const isIdle = phase === 'idle';
  const isAnswered = phase === 'result' || phase === 'sliding';
  const isBorderFading = phase === 'border-fading';
  const isGameOver = apiResult?.game_over ?? false;

  const countDisplay = !apiResult ? '?' : displayedCount;

  const countColor = isAnswered || isBorderFading
    ? apiResult?.correct
      ? 'text-green-500 dark:text-green-400'
      : 'text-red-500 dark:text-red-400'
    : 'text-gray-300 dark:text-gray-600';

  // Ring on the Card itself (only during result/sliding; border-fading uses the overlay)
  const resultRing = isAnswered
    ? apiResult?.correct
      ? 'ring-4 ring-green-400'
      : 'ring-4 ring-red-400'
    : '';

  // Pending card shows during result, sliding, and border-fading
  const showPending = !!(pendingRound && (isAnswered || isBorderFading));

  // Ring color for the fade overlay
  const ringOverlayColor = apiResult?.correct
    ? 'ring-green-400'
    : 'ring-red-400';

  // --- Render ---
  if (loading) {
    return (
      <GameLayout title="More or Less" showBackButton={false}>
        <div className="flex min-h-[400px] items-center justify-center">
          <LoadingSpinner />
        </div>
      </GameLayout>
    );
  }

  if (error || !session || !round) {
    return (
      <GameLayout title="More or Less">
        <div className="mx-auto max-w-2xl px-4 py-12">
          <Alert variant="error">{error}</Alert>
          <Button className="mt-4" onClick={initializeGame}>
            Try Again
          </Button>
        </div>
      </GameLayout>
    );
  }

  return (
    <GameLayout title="More or Less">
      <div className="mx-auto max-w-4xl px-4 py-12">
        {/* Score header */}
        <div className="mb-10 text-center">
          <div className="text-5xl font-bold text-blue-600 dark:text-blue-400">
            {session.score}
          </div>
          <div className="mt-2 text-gray-600 dark:text-gray-400">Score</div>
          <div className="mt-4 text-sm text-gray-500">
            Round {session.rounds_played + 1}
          </div>
          <div className="mt-1 text-sm text-orange-500">
            Streak: {session.streak}
          </div>
        </div>

        {/* Cards */}
        <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2">

          {/* Left card — stays fully visible; content swaps after slide covers it */}
          <Card className="p-6 text-center">
            {round.left_person.thumbnail_url && (
              <img
                src={round.left_person.thumbnail_url}
                alt={round.left_person.name}
                className="mx-auto mb-4 h-48 w-48 rounded-xl object-cover"
              />
            )}
            <div className="text-2xl font-bold">{round.left_person.name}</div>
            <div className="mt-4 text-5xl font-bold text-blue-600 dark:text-blue-400">
              {round.left_person.asset_count}
            </div>
            <div className="mt-2 text-gray-500">photos</div>
          </Card>

          {/* Right column: stacked cards */}
          <div className="relative">

            {/* Pending (next) card — behind the current card during result/sliding/border-fading.
                When the current card slides away it's already here, making the swap seamless. */}
            {showPending && pendingRound && (
              <div className="animate-card-peek absolute inset-0 z-0">
                <Card className="h-full p-6 text-center">
                  {pendingRound.right_person.thumbnail_url && (
                    <img
                      src={pendingRound.right_person.thumbnail_url}
                      alt={pendingRound.right_person.name}
                      className="mx-auto mb-4 h-48 w-48 rounded-xl object-cover"
                    />
                  )}
                  <div className="text-2xl font-bold">
                    {pendingRound.right_person.name}
                  </div>
                  <div className="mt-4 text-5xl font-bold text-gray-300 dark:text-gray-600">
                    ?
                  </div>
                  <div className="mt-2 text-gray-500">photos</div>
                </Card>
              </div>
            )}

            {/* Current right card — slides left to cover the left card */}
            <div ref={rightWrapperRef} className="relative z-10">
              <Card className={`p-6 text-center ${resultRing}`}>
                {round.right_person.thumbnail_url && (
                  <img
                    src={round.right_person.thumbnail_url}
                    alt={round.right_person.name}
                    className="mx-auto mb-4 h-48 w-48 rounded-xl object-cover"
                  />
                )}
                <div className="text-2xl font-bold">
                  {round.right_person.name}
                </div>
                <div
                  className={`mt-4 text-5xl font-bold transition-colors duration-300 ${countColor}`}
                >
                  {countDisplay}
                </div>
                <div className="mt-2 text-gray-500">photos</div>
              </Card>

              {/* Ring overlay that fades out after the card slides into place */}
              {isBorderFading && (
                <div
                  className={`animate-ring-fade pointer-events-none absolute inset-0 rounded-lg ring-4 ${ringOverlayColor}`}
                />
              )}
            </div>
          </div>
        </div>

        {/* Game over message */}
        {isGameOver && apiResult && (
          <Alert variant="error" className="mb-8">
            <div className="space-y-1">
              <div>✗ Wrong! {apiResult.revealed.name} has {apiResult.revealed.asset_count} photos</div>
              <div className="font-semibold">Game Over — Final score: {session.score}</div>
            </div>
          </Alert>
        )}

        {/* Action buttons */}
        {!isGameOver && (
          <div className="mb-8 flex gap-4">
            <Button
              className="flex-1"
              size="lg"
              disabled={!isIdle}
              onClick={() => handleGuess('less')}
            >
              ← Less
            </Button>
            <Button
              className="flex-1"
              size="lg"
              disabled={!isIdle}
              onClick={() => handleGuess('more')}
            >
              More →
            </Button>
          </div>
        )}

        {/* Play Again */}
        {isGameOver && (
          <div className="mb-8 text-center">
            <Button size="lg" onClick={initializeGame}>
              Play Again
            </Button>
          </div>
        )}

        {/* Quit */}
        <div className="text-center">
          <Button variant="secondary" onClick={handleQuit}>
            Quit Game
          </Button>
        </div>
      </div>
    </GameLayout>
  );
}
