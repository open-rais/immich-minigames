import { useEffect, useRef, useState } from "react"

import type { AlbumdleRoundOut } from "../../api/types/immichdle"
import { useCountUp } from "../shared/useCountUp"
import { AlbumCell } from "./AlbumCell"
import { AlbumDominantFaceCell } from "./AlbumDominantFaceCell"
import {
  ALBUM_CLUE_COLUMNS,
  ALBUM_CLUE_COLUMNS_AFTER_DOMINANT_FACE,
  ALBUM_CLUE_COLUMNS_BEFORE_DOMINANT_FACE,
} from "./albumGuessTableColumns"
import type { ClueResult } from "./clueColors"
import { ClueCell } from "./ClueCell"
import { CLUE_CELL_WRAPPER_CLASS, PERSON_COL, ROW_MIN_H_CLASS } from "./guessTableColumns"

// Same timing budget as AnimatedGuessRow.tsx (persondle's equivalent) - 6 total tiles either way
// (1 dominant-face + 5 generic here, vs 6 generic there), so the same constants keep the sequence
// feeling identical between modes.
const ENTER_MS = 350
const REVEAL_STEP_MS = 260
const HOLD_MS = 500
const COUNT_UP_DURATION_MS = 420
const ROW_GROW_ANIMATION_CLASS = "animate-[immichdle-row-grow_350ms_ease-out]"
const FADE_IN_ANIMATION_CLASS = "animate-[immichdle-fade-in_350ms_ease-out]"

// Total reveal steps: the dominant-face tile plus the 5 generic ones - revealed left-to-right in
// the same order they're rendered (see below): the 2 "before" columns, then dominant face, then
// the 3 "after" columns. The dominant-face tile's own slot index is fixed at
// ALBUM_CLUE_COLUMNS_BEFORE_DOMINANT_FACE.length (2), not hardcoded separately, so this can't drift
// from the render order if that split ever changes.
const DOMINANT_FACE_SLOT = ALBUM_CLUE_COLUMNS_BEFORE_DOMINANT_FACE.length
const TOTAL_STEPS = 1 + ALBUM_CLUE_COLUMNS.length

type RowPhase = "entering" | "revealing" | "done"

interface AlbumAnimatedGuessRowProps {
  round: AlbumdleRoundOut
  onDone: () => void
}

function AnimatedClueCell({ clue, revealed }: { clue: ClueResult; revealed: boolean }) {
  const isNumeric = clue.kind === "count" || clue.kind === "percent"
  const numericTarget = isNumeric && typeof clue.value === "number" ? clue.value : null
  const { value: countValue } = useCountUp(revealed ? numericTarget : null, COUNT_UP_DURATION_MS)

  if (!revealed) return <ClueCell clue={clue} pending />

  const displayClue: ClueResult = numericTarget !== null ? { ...clue, value: countValue } : clue
  return (
    <div className={`w-full ${FADE_IN_ANIMATION_CLASS}`}>
      <ClueCell clue={displayClue} />
    </div>
  )
}

// Albumdle's guess-reveal sequence - mirrors games/Immichdle/AnimatedGuessRow.tsx exactly, with
// the dominant-face tile (not a ClueCell) revealed in its ROADMAP.md-ordered position (3rd) rather
// than always first - see AlbumGuessTable.tsx for the same column order in the static table.
export function AlbumAnimatedGuessRow({ round, onDone }: AlbumAnimatedGuessRowProps) {
  const [phase, setPhase] = useState<RowPhase>("entering")
  const [revealCount, setRevealCount] = useState(0)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    const timer = setTimeout(() => setPhase("revealing"), ENTER_MS)
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    if (phase !== "revealing") return
    if (revealCount >= TOTAL_STEPS) {
      const timer = setTimeout(() => {
        setPhase("done")
        onDoneRef.current()
      }, HOLD_MS)
      return () => clearTimeout(timer)
    }
    const timer = setTimeout(() => setRevealCount((n) => n + 1), REVEAL_STEP_MS)
    return () => clearTimeout(timer)
  }, [phase, revealCount])

  const dominantFaceRevealed = DOMINANT_FACE_SLOT < revealCount

  return (
    <div className={`grid ${ROW_GROW_ANIMATION_CLASS}`} style={{ gridTemplateRows: "1fr" }}>
      <div className="min-h-0 overflow-hidden">
        <div className={`flex border-t border-line first:border-t-0 ${ROW_MIN_H_CLASS}`}>
          <div className={PERSON_COL}>
            <div className={`h-full ${FADE_IN_ANIMATION_CLASS}`}>
              <AlbumCell albumId={round.guess_album_id!} name={round.guess_album_name} />
            </div>
          </div>
          {ALBUM_CLUE_COLUMNS_BEFORE_DOMINANT_FACE.map((column, index) => (
            <div key={column.key} className={CLUE_CELL_WRAPPER_CLASS}>
              <AnimatedClueCell clue={column.compute(round)} revealed={index < revealCount} />
            </div>
          ))}
          <div className={CLUE_CELL_WRAPPER_CLASS}>
            {dominantFaceRevealed ? (
              <div className={`w-full ${FADE_IN_ANIMATION_CLASS}`}>
                <AlbumDominantFaceCell
                  personId={round.clues!.dominant_face_person_id}
                  name={round.clues!.dominant_face_name}
                  extraCount={round.clues!.dominant_face_extra_count}
                  comparison={round.clues!.dominant_face_comparison}
                />
              </div>
            ) : (
              <AlbumDominantFaceCell personId={null} name={null} extraCount={0} comparison={null} pending />
            )}
          </div>
          {ALBUM_CLUE_COLUMNS_AFTER_DOMINANT_FACE.map((column, index) => (
            <div key={column.key} className={CLUE_CELL_WRAPPER_CLASS}>
              <AnimatedClueCell
                clue={column.compute(round)}
                revealed={DOMINANT_FACE_SLOT + 1 + index < revealCount}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
