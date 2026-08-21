import type { ReactNode } from "react"

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
  children: ReactNode
}

export function TriviumOption({ state, disabled, onClick, children }: TriviumOptionProps) {
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
