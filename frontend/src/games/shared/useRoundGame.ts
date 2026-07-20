import { useEffect, useRef, useState } from "react"

import { createGame } from "../../api/games"
import type { PlayRoundOut, RoundOut } from "../../api/types"

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

  // Synchronous re-entrancy guards - a click handler can fire twice before React re-renders (e.g. a
  // fast double-click), so state alone isn't enough to stop a second network call; these refs are
  // checked and set immediately, no render involved.
  const guessInFlightRef = useRef(false)
  const startInFlightRef = useRef(false)
  // Bumped on every new start/guess and on "Back" - a response for a request that's no longer
  // current (e.g. the user hit Back while a guess was still in flight) is ignored when it arrives.
  const requestTokenRef = useRef(0)
  // Kept in a ref so the reveal-hold effect below can call the latest onNewRound without listing it
  // as a dependency (which would re-run the timer on every render).
  const onNewRoundRef = useRef(onNewRound)
  onNewRoundRef.current = onNewRound

  async function startGame() {
    if (startInFlightRef.current) return
    startInFlightRef.current = true
    const token = ++requestTokenRef.current
    setBusy(true)
    try {
      const g = await createGame(gameType, mode)
      if (requestTokenRef.current !== token) return
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
      if (requestTokenRef.current === token) setScreen("error")
    } finally {
      startInFlightRef.current = false
      if (requestTokenRef.current === token) setBusy(false)
    }
  }

  async function submitGuess(guess: TGuess) {
    if (guessInFlightRef.current || !game || !round || phase !== "guessing") return
    guessInFlightRef.current = true
    const token = ++requestTokenRef.current
    setBusy(true)
    setPhase("submitting")
    try {
      const result = await playRound(game.id, round.id, guess)
      if (requestTokenRef.current !== token) return
      if (!isRound(result.answered_round) || (result.next_round && !isRound(result.next_round))) {
        setScreen("error")
        return
      }
      setGame((g) => (g ? { ...g, score: result.score, finished: result.finished } : g))
      setRound(result.answered_round)
      setPendingNextRound(result.next_round as TRound | null)
      setPhase("revealed")
    } catch {
      if (requestTokenRef.current === token) setScreen("error")
    } finally {
      guessInFlightRef.current = false
      if (requestTokenRef.current === token) setBusy(false)
    }
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
    requestTokenRef.current++ // discard any in-flight guess/start response that arrives later
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
