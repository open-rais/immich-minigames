import { useEffect, useRef, useState } from "react"

import { createGame } from "../../api/games"
import type { PlayRoundOut, RoundOut } from "../../api/types"
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
}

export function useRoundGame<TRound extends RoundOut, TGuess>({
  gameType,
  mode,
  revealHoldMs,
  isRound,
  playRound,
  onNewRound,
}: UseRoundGameConfig<TRound, TGuess>) {
  const [screen, setScreen] = useState<Screen>("idle")
  const [busy, setBusy] = useState(false)
  const [game, setGame] = useState<GameState | null>(null)
  const [round, setRound] = useState<TRound | null>(null)
  const [pendingNextRound, setPendingNextRound] = useState<TRound | null>(null)
  const [phase, setPhase] = useState<RoundPhase>("guessing")

  const { isCurrent, guarded, discardInFlight } = useGuardedRequests()
  // One in-flight ref per action - start vs guess don't need to block each other, but each needs its
  // own re-entrancy guard against a fast double-click firing before React re-renders.
  const guessInFlightRef = useRef(false)
  const startInFlightRef = useRef(false)
  // Kept in a ref so the reveal-hold effect below can call the latest onNewRound without listing it
  // as a dependency (which would re-run the timer on every render).
  const onNewRoundRef = useRef(onNewRound)
  onNewRoundRef.current = onNewRound

  async function startGame() {
    await guarded(startInFlightRef, async (token) => {
      setBusy(true)
      try {
        const g = await createGame(gameType, mode)
        if (!isCurrent(token)) return
        const firstRound = g.rounds[g.rounds.length - 1]
        if (!isRound(firstRound)) {
          setScreen("error")
          return
        }
        setGame({ id: g.id, score: g.score, finished: g.finished, totalRounds: g.total_rounds, totalPeople: g.total_people })
        setRound(firstRound)
        setPendingNextRound(null)
        onNewRoundRef.current()
        setPhase("guessing")
        setScreen("playing")
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
    startGame,
    submitGuess,
    backToIdle,
  }
}
