import type { ReactNode } from "react"

import { PersonAvatar } from "../shared/PersonAvatar"

// One of the 4 alternatives - deliberately its own component rather than a Button.tsx variant:
// none of Button's three variants fit (primary is the CTA indigo this is explicitly meant to
// avoid, secondary reads too flat/neutral for 4 options that need to be told apart at a glance,
// danger is semantically reserved for errors elsewhere in the app), and it needs post-answer
// reveal states Button has no concept of.
export type TriviumOptionState = "idle" | "pending" | "correct" | "wrong" | "muted"

// Fluid, like the question (see TriviumBoard.tsx's QUESTION_FONT_SIZE). `break-words` below is
// what keeps a long alternative - a full date spelled out in Spanish, a three-part name - inside
// its button; the size doesn't have to.
const LABEL_FONT_SIZE = "clamp(1.1rem, min(4vw, 5dvh), 1.5rem)"
const CAPTION_FONT_SIZE = "clamp(0.8rem, min(3vw, 4dvh), 1.25rem)"

const STATE_CLASS: Record<TriviumOptionState, string> = {
  // Filled with the app's existing "badge" family (bg-badge-bg/text-badge-value) - indigo-tinted
  // like everything else in the app, but not the CTA indigo (--color-primary) itself, and reads
  // better at a glance than a hollow bordered button would for 4 options at once.
  idle: "border-line bg-badge-bg text-badge-value hover:bg-badge-bg-hover",
  // The option the player just clicked, while the guess is in flight (TriviumGame.tsx's
  // phase === "submitting") - same fill as idle, plus a ring so it reads as "selected" without
  // moving the layout (every state already has a `border` of the same width, `ring` sits outside
  // it instead of resizing the box).
  pending: "border-primary bg-badge-bg text-badge-value ring-2 ring-primary",
  // Revealed after answering: green for the right alternative, red for the wrong one the player
  // picked - reusing the same clue-match/clue-miss tokens Immichdle's clue tiles use (index.css
  // documents those as generic on purpose, for exactly this kind of reuse).
  correct: "border-transparent bg-clue-match text-white",
  wrong: "border-transparent bg-clue-miss text-white",
  // Every other option once the round is revealed, every option before alternatives are shown
  // (see TriviumGame.tsx's showAlternatives gate), and every option but the pending one while a
  // guess is in flight - present but visually backed off.
  muted: "border-line bg-badge-bg text-badge-value opacity-50",
}

interface TriviumOptionProps {
  state: TriviumOptionState
  disabled?: boolean
  onClick?: () => void
  // Set (even to null, while still loading/unresolved) for a question whose alternatives are
  // people (photos_total_assets/photos_together/mixed_name_to_face) - renders their photo above
  // the name instead of the plain text button. Left unset for every other question_kind.
  photoUrl?: string | null
  // mixed_name_to_face ("who is {name}") is meant to be answered by face alone - printing the name
  // under each candidate would just hand over the answer. photos_total_assets/photos_together
  // (where the name *is* the thing being compared) keep their caption; this only ever applies
  // alongside photoUrl.
  hideCaption?: boolean
  children: ReactNode
}

export function TriviumOption({ state, disabled, onClick, photoUrl, hideCaption, children }: TriviumOptionProps) {
  if (photoUrl !== undefined) {
    return (
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-label={hideCaption && typeof children === "string" ? children : undefined}
        className={`flex w-full flex-col items-center gap-2 rounded-2xl border p-2 text-center transition-colors disabled:cursor-not-allowed sm:p-3 md:gap-3 md:rounded-3xl md:p-4 short-wide:gap-1 short-wide:p-2 ${STATE_CLASS[state]}`}
      >
        <PersonAvatar src={photoUrl} alt="" size="fluid" />
        {!hideCaption && (
          <span className="font-bold break-words" style={{ fontSize: CAPTION_FONT_SIZE }}>
            {children}
          </span>
        )}
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      // Height follows the screen's height, not a fixed size per breakpoint: a tall screen gets
      // generous tap targets, a short one gives that height back to the round's media, which is
      // the only other thing competing for it (a fixed md:min-h-28 used to leave a location photo
      // ~100px tall on a 1280x720 laptop). The floor is a comfortable 48px tap target.
      className={`flex min-h-[clamp(3rem,8dvh,6rem)] w-full items-center justify-center rounded-2xl border px-3 py-2 font-bold break-words transition-colors disabled:cursor-not-allowed sm:px-5 sm:py-3 md:rounded-3xl md:px-8 short-wide:px-4 short-wide:py-2 ${STATE_CLASS[state]}`}
      style={{ fontSize: LABEL_FONT_SIZE }}
    >
      {children}
    </button>
  )
}
