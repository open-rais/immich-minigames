import type { ReactNode } from "react"

import { PersonAvatar } from "../shared/PersonAvatar"

// One of the 4 alternatives - deliberately its own component rather than a Button.tsx variant:
// none of Button's three variants fit (primary is the CTA indigo this is explicitly meant to
// avoid, secondary reads too flat/neutral for 4 options that need to be told apart at a glance,
// danger is semantically reserved for errors elsewhere in the app), and it needs post-answer
// reveal states Button has no concept of.
export type TriviumOptionState = "idle" | "correct" | "wrong" | "muted"

const STATE_CLASS: Record<TriviumOptionState, string> = {
  // Filled with the app's existing "badge" family (bg-badge-bg/text-badge-value) - indigo-tinted
  // like everything else in the app, but not the CTA indigo (--color-primary) itself, and reads
  // better at a glance than a hollow bordered button would for 4 options at once.
  idle: "border-line bg-badge-bg text-badge-value hover:bg-badge-bg-hover",
  // Revealed after answering: green for the right alternative, red for the wrong one the player
  // picked - reusing the same clue-match/clue-miss tokens Immichdle's clue tiles use (index.css
  // documents those as generic on purpose, for exactly this kind of reuse).
  correct: "border-transparent bg-clue-match text-white",
  wrong: "border-transparent bg-clue-miss text-white",
  // Every other option once the round is revealed, and every option before alternatives are shown
  // (see TriviumGame.tsx's showAlternatives gate) - present but visually backed off.
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
        className={`flex w-full flex-col items-center gap-2 rounded-2xl border p-3 text-center transition-colors disabled:cursor-not-allowed md:gap-3 md:rounded-3xl md:p-4 ${STATE_CLASS[state]}`}
      >
        <PersonAvatar src={photoUrl} alt="" size="lg" />
        {!hideCaption && <span className="text-base font-bold md:text-xl">{children}</span>}
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`w-full rounded-2xl border px-5 py-4 text-lg font-bold transition-colors disabled:cursor-not-allowed md:min-h-28 md:rounded-3xl md:px-8 md:py-6 md:text-2xl ${STATE_CLASS[state]}`}
    >
      {children}
    </button>
  )
}
