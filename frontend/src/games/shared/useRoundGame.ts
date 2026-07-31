import { useEffect, useRef, useState } from "react"

import { createDailyGame, getDailyStatus } from "../../api/daily"
import { apiErrorStatus } from "../../api/errors"
import { createGame, getCurrentGame, getGame } from "../../api/games"
import type { GameOut, PlayRoundOut, RoundOut } from "../../api/types"
import { useGuardedRequests } from "./useGuardedRequests"

// Only the fields that stay live for the whole game. The full GameOut also carries `rounds`, but
// after the first round it would go stale (guesses update score/finished, not the round list), so
// we deliberately don't keep it - a stale `game.rounds` would be a trap for the finished screen.
interface GameState {
  id: string
  score: number
  finished: boolean
  // Admin feature (ADMIN-FEATURE.md point #4) - the backend's live configured total for this game
  // (Geoguessr/Dateguessr: total_rounds, WhosThatPerson: total_people; undefined for games with
  // neither). Captured once at game start, same as the fields above - unlike `rounds`, an admin
  // changing this setting mid-game shouldn't retroactively change what a game already in progress
  // displays as its total.
  totalRounds?: number | null
  totalPeople?: number | null
}

// Shared state machine for the "fixed number of rounds, one picker per round, auto-advance after a
// reveal hold" games (Geoguessr, Dateguessr). Both were near-identical copies; the only real
// differences are the per-round guess input (a map pin vs. a picked date) and which round variant
// comes back, so those are the type/callback parameters below. The component still owns its guess
// input state and rendering - this hook owns everything else (screens, phases, the concurrency
// guards, and the reveal-hold auto-advance).

export type Screen = "idle" | "playing" | "finished" | "error"
export type RoundPhase = "guessing" | "submitting" | "revealed"

interface UseRoundGameConfig<TRound extends RoundOut, TGuess> {
  gameType: string
  mode: string
  revealHoldMs: number
  // Narrows a RoundOut coming off the wire to this game's own round variant. A false result means
  // the backend returned something unexpected for this component, which becomes the error screen.
  isRound: (round: RoundOut) => round is TRound
  playRound: (gameId: string, roundId: string, guess: TGuess) => Promise<PlayRoundOut>
  // Resets the component-owned guess input whenever a fresh round becomes active (game start and
  // each auto-advance).
  onNewRound: () => void
  // Roadmap #e - fired once, only when resumeGame() picks an in-progress game back up (never on a
  // fresh startGame()), with the full fetched GameOut - the hook-point a caller with extra
  // accumulated state derived from round history (e.g. WhosThatPersonGame's "N of 15 people"
  // counter) needs to seed itself from every already-answered round, not just the resumed pending
  // one. Games with no such state (Geoguessr, Dateguessr) simply omit it.
  onResume?: (game: GameOut) => void
  // Roadmap #G - true when this instance is playing today's daily challenge (menu/
  // DailyGameRoute.tsx) instead of a normal game. Changes only the wiring below: which endpoint
  // creates a game, where the idle-screen "has an active game" check reads from (GET /daily's
  // status instead of get_current_game, which excludes daily games by design - see
  // docs/TODO/DAILY-GAMES.md §4.5), and that an already-finished daily jumps straight to the
  // finished screen instead of ever offering "Jugar" again.
  daily?: boolean
}

export function useRoundGame<TRound extends RoundOut, TGuess>({
  gameType,
  mode,
  revealHoldMs,
  isRound,
  playRound,
  onNewRound,
  onResume,
  daily = false,
}: UseRoundGameConfig<TRound, TGuess>) {
  const [screen, setScreen] = useState<Screen>("idle")
  const [busy, setBusy] = useState(false)
  const [game, setGame] = useState<GameState | null>(null)
  const [round, setRound] = useState<TRound | null>(null)
  const [pendingNextRound, setPendingNextRound] = useState<TRound | null>(null)
  const [phase, setPhase] = useState<RoundPhase>("guessing")
  // Roadmap #e - whether the current player has an unfinished game for this (gameType, mode);
  // null while the idle-screen check below is still in flight, which IdleScreen treats the same
  // as false (an accepted brief "plain layout, then Continue pops in" flash).
  const [hasCurrentGame, setHasCurrentGame] = useState<boolean | null>(null)
  // Roadmap #G - the daily game's id, known from GET /daily's status before the player has done
  // anything - resumeGame() reads this instead of calling getCurrentGame (which never returns a
  // daily game).
  const dailyGameIdRef = useRef<string | null>(null)
  // Bumped when the idle-screen status needs re-fetching while the screen is already "idle" -
  // today only the daily 409 fallback in startGame below (docs/TODO/DAILY-GAMES.md §4.7).
  const [idleRefresh, setIdleRefresh] = useState(0)

  const { isCurrent, guarded, discardInFlight } = useGuardedRequests()
  // One in-flight ref per action - start vs guess don't need to block each other, but each needs its
  // own re-entrancy guard against a fast double-click firing before React re-renders.
  const guessInFlightRef = useRef(false)
  const startInFlightRef = useRef(false)
  // Kept in a ref so the reveal-hold effect below can call the latest onNewRound without listing it
  // as a dependency (which would re-run the timer on every render).
  const onNewRoundRef = useRef(onNewRound)
  onNewRoundRef.current = onNewRound
  const onResumeRef = useRef(onResume)
  onResumeRef.current = onResume

  // Re-checked every time the idle screen is (re-)shown - e.g. after backToIdle, not just on mount.
  useEffect(() => {
    if (screen !== "idle") return
    let cancelled = false

    if (daily) {
      getDailyStatus()
        .then((status) => {
          if (cancelled) return
          const modeStatus = status.modes.find((m) => m.game_type === gameType && m.mode === mode)
          dailyGameIdRef.current = modeStatus?.game_id ?? null

          if (modeStatus?.status === "finished" && modeStatus.game_id) {
            setHasCurrentGame(false)
            getGame(modeStatus.game_id)
              .then((g) => {
                if (cancelled) return
                setGame({
                  id: g.id,
                  score: g.score,
                  finished: true,
                  totalRounds: g.total_rounds,
                  totalPeople: g.total_people,
                })
                setScreen("finished")
              })
              .catch(() => {
                if (!cancelled) setScreen("error")
              })
            return
          }
          setHasCurrentGame(modeStatus?.status === "in_progress")
        })
        .catch(() => {
          if (!cancelled) setHasCurrentGame(false)
        })
      return () => {
        cancelled = true
      }
    }

    getCurrentGame(gameType, mode)
      .then((g) => {
        if (!cancelled) setHasCurrentGame(g !== null)
      })
      .catch(() => {
        if (!cancelled) setHasCurrentGame(false)
      })
    return () => {
      cancelled = true
    }
  }, [screen, gameType, mode, daily, idleRefresh])

  // Shared by startGame (fresh GameOut from createGame) and resumeGame (an existing one from
  // getCurrentGame) - both hand off a GameOut whose last round is the current pending one (true by
  // construction for a fresh game, and true for an unfinished one per games/base.py's play_round,
  // which always appends a fresh pending round unless the game just finished).
  function applyGame(g: GameOut): boolean {
    const currentRound = g.rounds[g.rounds.length - 1]
    if (!isRound(currentRound)) return false
    setGame({
      id: g.id,
      score: g.score,
      finished: g.finished,
      totalRounds: g.total_rounds,
      totalPeople: g.total_people,
    })
    setRound(currentRound)
    setPendingNextRound(null)
    setPhase("guessing")
    setScreen("playing")
    return true
  }

  async function startGame() {
    await guarded(startInFlightRef, async (token) => {
      setBusy(true)
      try {
        const g = daily ? await createDailyGame(gameType, mode) : await createGame(gameType, mode)
        if (!isCurrent(token)) return
        if (!applyGame(g)) {
          setScreen("error")
          return
        }
        onNewRoundRef.current()
      } catch (err) {
        if (!isCurrent(token)) return
        if (daily && apiErrorStatus(err) === 409) {
          // Today's attempt was consumed between the idle status check and this create (another
          // tab/device) - re-run the status check instead of showing a generic error; it lands on
          // the finished (or in-progress) state, the "ya jugado" behavior of DAILY-GAMES.md §4.7.
          setHasCurrentGame(null)
          setIdleRefresh((n) => n + 1)
          return
        }
        setScreen("error")
      } finally {
        if (isCurrent(token)) setBusy(false)
      }
    })
  }

  // Roadmap #e - "Continuar" button's action: picks the player's existing unfinished game back up
  // instead of creating a new one.
  async function resumeGame() {
    await guarded(startInFlightRef, async (token) => {
      setBusy(true)
      try {
        const g = daily
          ? dailyGameIdRef.current
            ? await getGame(dailyGameIdRef.current)
            : null
          : await getCurrentGame(gameType, mode)
        if (!isCurrent(token) || !g) return
        if (!applyGame(g)) {
          setScreen("error")
          return
        }
        onResumeRef.current?.(g)
        onNewRoundRef.current()
      } catch {
        if (isCurrent(token)) setScreen("error")
      } finally {
        if (isCurrent(token)) setBusy(false)
      }
    })
  }

  async function submitGuess(guess: TGuess) {
    if (!game || !round || phase !== "guessing") return
    await guarded(guessInFlightRef, async (token) => {
      setBusy(true)
      setPhase("submitting")
      try {
        const result = await playRound(game.id, round.id, guess)
        if (!isCurrent(token)) return
        if (!isRound(result.answered_round) || (result.next_round && !isRound(result.next_round))) {
          setScreen("error")
          return
        }
        setGame((g) => (g ? { ...g, score: result.score, finished: result.finished } : g))
        setRound(result.answered_round)
        setPendingNextRound(result.next_round as TRound | null)
        setPhase("revealed")
      } catch {
        if (isCurrent(token)) setScreen("error")
      } finally {
        if (isCurrent(token)) setBusy(false)
      }
    })
  }

  // Once a guess is revealed, wait a beat so the player can read the result, then auto-advance to
  // the next round (or the finished screen) - no explicit "next round" click.
  useEffect(() => {
    if (phase !== "revealed") return
    const timer = setTimeout(() => {
      if (!game || game.finished || !pendingNextRound) {
        setScreen("finished")
        return
      }
      setRound(pendingNextRound)
      setPendingNextRound(null)
      onNewRoundRef.current()
      setPhase("guessing")
    }, revealHoldMs)
    return () => clearTimeout(timer)
  }, [phase, game, pendingNextRound, revealHoldMs])

  function backToIdle() {
    discardInFlight() // discard any in-flight guess/start response that arrives later
    setScreen("idle")
  }

  return {
    screen,
    busy,
    game,
    round,
    phase,
    revealed: phase === "revealed",
    hasCurrentGame,
    startGame,
    resumeGame,
    submitGuess,
    backToIdle,
  }
}
