import { useState } from "react"

import type { GameOut, RoundOut } from "../../api/types"

interface RoundStepperState<T extends RoundOut> {
  round: T
  index: number
  total: number
  prev: () => void
  next: () => void
}

// The "fullscreen" rounds-review shape shared by GeoguessrRounds/DateguessrRounds/
// WhosThatPersonRounds - narrow game.rounds to this game's own round type, drop any round still
// pending an answer (a game reached mid-play by URL), and step through what's left one at a time.
// TimelineRounds doesn't use this - it shows the whole finished board at once instead of a stepper
// (see its own docstring).
export function useRoundStepper<T extends RoundOut>(
  game: GameOut,
  isRound: (round: RoundOut) => round is T,
  isAnswered: (round: T) => boolean,
): RoundStepperState<T> | null {
  const [index, setIndex] = useState(0)

  const rounds = game.rounds.filter(isRound).filter(isAnswered)
  const round = rounds[index]
  if (!round) return null

  return {
    round,
    index,
    total: rounds.length,
    prev: () => setIndex((i) => Math.max(i - 1, 0)),
    next: () => setIndex((i) => Math.min(i + 1, rounds.length - 1)),
  }
}
