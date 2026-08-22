import { useEffect, useRef, useState } from "react"

import type { GameOut, PlayRoundOut, RoundOut } from "../../api/types/common"
import { useGameSession } from "./useGameSession"

// Only the fields that stay live for the whole game. The full GameOut also carries `rounds`, but
// after the first round it would go stale (guesses update score/finished, not the round list), so
// we deliberately don't keep it - a stale `game.rounds` would be a trap for the finished screen.
interface GameState {
  id: string
  score: number
  finished: boolean
  // The backend's live configured total for this game
  // (Geoguessr/Dateguessr: total_rounds, WhosThatPerson: total_people; undefined for games with
  // neither). Captured once at game start, same as the fields above - unlike `rounds`, an admin
  // changing this setting mid-game shouldn't retroactively change what a game already in progress
  // displays as its total.
  totalRounds?: number | null
  totalPeople?: number | null
  faceBoxGrowth?: number | null
  // Trivium's per-round answer window in seconds (see api/types/common.ts's GameOut) - the same
  // "captured once at game start" rationale as the fields above: an admin changing this setting
  // mid-game shouldn't retroactively change the countdown a round already in progress runs on.
  answerTimeSeconds?: number | null
}

// Round-flow layer for the "fixed number of rounds, one picker per round, auto-advance after a
// reveal hold" games (Geoguessr, Dateguessr, Timeline, WhosThatPerson), built on top of
// useGameSession for the screen/busy/daily/start/resume/backToIdle
// lifecycle those games share with every other game. This hook owns what's specific to their round
// shape: round/pendingNextRound/phase state, the reveal-hold auto-advance, and submitGuess. The
// component still owns its guess input state and rendering.

export type { Screen } from "./useGameSession"
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
  // Fired once, only when resumeGame() picks an in-progress game back up (never on a
  // fresh startGame()), with the full fetched GameOut - the hook-point a caller with extra
  // accumulated state derived from round history (e.g. WhosThatPersonGame's "N of 15 people"
  // counter) needs to seed itself from every already-answered round, not just the resumed pending
  // one. Games with no such state (Geoguessr, Dateguessr) simply omit it.
  onResume?: (game: GameOut) => void
  // See useGameSession's own docstring for what this changes.
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
  const [game, setGame] = useState<GameState | null>(null)
  const [round, setRound] = useState<TRound | null>(null)
  const [pendingNextRound, setPendingNextRound] = useState<TRound | null>(null)
  const [phase, setPhase] = useState<RoundPhase>("guessing")

  // One in-flight ref for guesses - start/resume have their own inside useGameSession, and don't
  // need to block a guess (they can't overlap in practice, but each action guards independently).
  const guessInFlightRef = useRef(false)
  // Kept in a ref so the reveal-hold effect below can call the latest onNewRound without listing it
  // as a dependency (which would re-run the timer on every render).
  const onNewRoundRef = useRef(onNewRound)
  onNewRoundRef.current = onNewRound
  const onResumeRef = useRef(onResume)
  onResumeRef.current = onResume

  // Shared by startGame (fresh GameOut from createGame) and resumeGame (an existing one from
  // getCurrentGame) - both hand off a GameOut whose last round is the current pending one (true by
  // construction for a fresh game, and true for an unfinished one per games/base.py's play_round,
  // which always appends a fresh pending round unless the game just finished).
  function applyGame(g: GameOut, isResume: boolean): boolean {
    const currentRound = g.rounds[g.rounds.length - 1]
    if (!isRound(currentRound)) return false
    setGame({
      id: g.id,
      score: g.score,
      finished: g.finished,
      totalRounds: g.total_rounds,
      totalPeople: g.total_people,
      faceBoxGrowth: g.face_box_growth,
      answerTimeSeconds: g.answer_time_seconds,
    })
    setRound(currentRound)
    setPendingNextRound(null)
    setPhase("guessing")
    if (isResume) onResumeRef.current?.(g)
    onNewRoundRef.current()
    return true
  }

  function hydrateFinishedDaily(g: GameOut): boolean {
    setGame({
      id: g.id,
      score: g.score,
      finished: true,
      totalRounds: g.total_rounds,
      totalPeople: g.total_people,
      faceBoxGrowth: g.face_box_growth,
      answerTimeSeconds: g.answer_time_seconds,
    })
    return true
  }

  const {
    screen,
    setScreen,
    busy,
    setBusy,
    hasCurrentGame,
    startGame,
    resumeGame,
    backToIdle,
    markDailyFinished,
    markRecordBeaten,
    isCurrent,
    guarded,
  } = useGameSession({ gameType, mode, daily, applyGame, hydrateFinishedDaily })

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
        if (result.finished) {
          markDailyFinished(game.id, result.score)
          markRecordBeaten(result.score)
        }
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
  }, [phase, game, pendingNextRound, revealHoldMs, setScreen])

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
