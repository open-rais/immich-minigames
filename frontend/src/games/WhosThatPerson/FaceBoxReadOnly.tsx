import { personThumbnailUrl } from "../../api/games"
import type { HiddenFaceOut } from "../../api/types"
import { boxStyle } from "./faceBoxMath"

export type FaceBoxMode = "yourAnswer" | "real"

interface FaceBoxReadOnlyProps {
  face: HiddenFaceOut
  mode: FaceBoxMode
}

// Read-only counterpart to IncognitoPhoto.tsx's internal FaceBox, for the rounds review
// (ROUNDS-VIEW.md roadmap #10, §4.6) - same box geometry (faceBoxMath.ts), but none of that
// component's popover/anchor/tap logic, which this doesn't need at all: just one of two static
// end-states, chosen by the "Tu respuesta"/"Real" toggle.
export function FaceBoxReadOnly({ face, mode }: FaceBoxReadOnlyProps) {
  const yourAnswer = mode === "yourAnswer"
  // "Real" mirrors FaceBox's own revealed border coloring; "Tu respuesta" is the covered/unrevealed
  // state, which never carries a verdict color.
  const borderClass = yourAnswer
    ? "border-white/80"
    : face.correct
      ? "border-clue-match"
      : "border-clue-miss"
  const label = yourAnswer ? (face.guess_person_name ?? "?") : face.person_name

  return (
    <div className="absolute" style={boxStyle(face)}>
      <div className="relative h-full w-full">
        <div className={`h-full w-full overflow-hidden rounded-md border-2 ${borderClass}`}>
          {/* "Real" leaves this empty - the real, uncensored photo is already showing through
              underneath, nothing left to reveal. */}
          {yourAnswer &&
            (face.guess_person_id ? (
              <img
                src={personThumbnailUrl(face.guess_person_id)}
                alt=""
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="h-full w-full bg-blackout" />
            ))}
        </div>

        {label && (
          <span className="pointer-events-none absolute top-full left-1/2 z-10 mt-1.5 -translate-x-1/2 rounded-full bg-surface px-2.5 py-1 text-[11px] font-bold whitespace-nowrap text-ink shadow-card">
            {label}
          </span>
        )}
      </div>
    </div>
  )
}
