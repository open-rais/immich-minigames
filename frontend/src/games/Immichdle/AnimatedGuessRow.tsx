import { useEffect, useRef, useState } from "react"

import type { ImmichdleRoundOut } from "../../api/types/immichdle"
import { useCountUp } from "../shared/useCountUp"
import type { ClueResult } from "./clueColors"
import { ClueCell } from "./ClueCell"
import {
  CLUE_CELL_WRAPPER_CLASS,
  CLUE_COLUMNS,
  PERSON_COL,
  ROW_MIN_H_CLASS,
} from "./guessTableColumns"
import { PersonCell } from "./PersonCell"

// Timing budget for the guess-reveal sequence (§7 of docs/TODO/UI-ENHANCEMENTS.md, [DECISIÓN F2] -
// fixed after eyeballing it on screen, not derived from anything). Total for one row is roughly
// ENTER_MS + CLUE_COLUMNS.length * REVEAL_STEP_MS + HOLD_MS ≈ 2.5s, in line with the other games'
// own REVEAL_HOLD_MS (2400ms Geo/Date, 2800ms WTP).
const ENTER_MS = 350
const REVEAL_STEP_MS = 260
const HOLD_MS = 500
const COUNT_UP_DURATION_MS = 420
// Kept in sync with index.css's `immichdle-row-grow`/`immichdle-fade-in` keyframe durations by
// hand - same pixel/duration coupling CLAUDE.md warns about, just for a duration instead of a pixel.
const ROW_GROW_ANIMATION_CLASS = "animate-[immichdle-row-grow_350ms_ease-out]"
const FADE_IN_ANIMATION_CLASS = "animate-[immichdle-fade-in_350ms_ease-out]"

type RowPhase = "entering" | "revealing" | "done"

interface AnimatedGuessRowProps {
  round: ImmichdleRoundOut
  // Fired exactly once, when the whole sequence (grow-in + all clues revealed + hold) finishes.
  // ImmichdleGame.tsx uses this to clear `animatingRoundId` and, if this was the game's last guess,
  // advance to the finished screen.
  onDone: () => void
}

// One clue tile within the sequence - a plain pending square (ClueCell's own `pending` state) until
// its turn, then fades in at its final color/value. Its own component, not inlined in the .map()
// below, because the count-up needs a hook call and hooks can't live inside a callback.
function AnimatedClueCell({ clue, revealed }: { clue: ClueResult; revealed: boolean }) {
  const isNumeric = clue.kind === "count" || clue.kind === "percent"
  const numericTarget = isNumeric && typeof clue.value === "number" ? clue.value : null
  // Only starts counting once `revealed` flips true - held at 0/not-done before that, same "target
  // null means hold" contract MoreOrLessGame already relies on.
  const { value: countValue } = useCountUp(revealed ? numericTarget : null, COUNT_UP_DURATION_MS)

  if (!revealed) return <ClueCell clue={clue} pending />

  // For kind: "date"/"text" numericTarget is null, so this is just `clue` unchanged - the count-up
  // only ever touches the columns where "the number writes in" actually makes sense ([DECISIÓN F1]).
  const displayClue: ClueResult = numericTarget !== null ? { ...clue, value: countValue } : clue
  return (
    // w-full: CLUE_CELL_WRAPPER_CLASS is a flex container (to center the pending tile within
    // ROW_MIN_H_CLASS's extra height), so this wrapper - a flex item now, not a plain block child -
    // shrink-wraps to its content by default instead of spanning the column's full width. Without an
    // explicit w-full here, ClueCell's own `aspect-square w-full` had nothing but that shrunk box to
    // resolve 100% against, so the tile collapsed down to just the number's own tiny content size.
    <div className={`w-full ${FADE_IN_ANIMATION_CLASS}`}>
      <ClueCell clue={displayClue} />
    </div>
  )
}

// The currently-entering row of GuessTable's live-play table (games/Immichdle/GuessTable.tsx) -
// pushes the table down as it grows to its natural height (a CSS grid-rows animation, not a
// measured pixel push - see index.css), then reveals its 6 clue tiles left-to-right one at a time.
// Never used in the rounds-review table (ImmichdleRounds.tsx never sets an animatingRoundId), so
// there's no `target`/actions-column handling here - GuessTable's own static row already covers that
// case, this component only ever renders during live play.
export function AnimatedGuessRow({ round, onDone }: AnimatedGuessRowProps) {
  const [phase, setPhase] = useState<RowPhase>("entering")
  const [revealCount, setRevealCount] = useState(0)
  // Ref, not a dependency - onDone is a fresh closure every ImmichdleGame render, and listing it
  // would restart this row's own timers whenever the parent re-renders for an unrelated reason.
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    const timer = setTimeout(() => setPhase("revealing"), ENTER_MS)
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    if (phase !== "revealing") return
    if (revealCount >= CLUE_COLUMNS.length) {
      const timer = setTimeout(() => {
        setPhase("done")
        onDoneRef.current()
      }, HOLD_MS)
      return () => clearTimeout(timer)
    }
    const timer = setTimeout(() => setRevealCount((n) => n + 1), REVEAL_STEP_MS)
    return () => clearTimeout(timer)
  }, [phase, revealCount])

  return (
    <div className={`grid ${ROW_GROW_ANIMATION_CLASS}`} style={{ gridTemplateRows: "1fr" }}>
      <div className="min-h-0 overflow-hidden">
        <div className={`flex border-t border-line first:border-t-0 ${ROW_MIN_H_CLASS}`}>
          <div className={PERSON_COL}>
            {/* h-full so PersonCell's own h-full (which centers its content vertically) has an
                actual height to resolve against - without it this wrapper sits at auto/content
                height, so PersonCell's h-full falls back to auto too and the whole cell collapses
                to the top of the row instead of centering. */}
            <div className={`h-full ${FADE_IN_ANIMATION_CLASS}`}>
              <PersonCell personId={round.guess_person_id!} name={round.guess_person_name} />
            </div>
          </div>
          {CLUE_COLUMNS.map((column, index) => (
            <div key={column.key} className={CLUE_CELL_WRAPPER_CLASS}>
              <AnimatedClueCell clue={column.compute(round)} revealed={index < revealCount} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
