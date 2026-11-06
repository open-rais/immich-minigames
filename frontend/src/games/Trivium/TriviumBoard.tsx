import type { ReactNode } from "react"

import { AssetPhoto } from "../shared/AssetPhoto"
import { PersonAvatar } from "../shared/PersonAvatar"
import type { QuestionSegment } from "./questionText"

// The round's media, already resolved to a src: Trivium only ever shows one subject face, one
// asset photo, or nothing above the question.
export type TriviumBoardMedia =
  | { kind: "none" }
  | { kind: "person"; src: string | null }
  | { kind: "asset"; src: string; onReadyChange?: (ready: boolean) => void }

interface TriviumBoardProps {
  media: TriviumBoardMedia
  questionWords: QuestionSegment[]
  // How many of questionWords are visible - the live game's word-by-word reveal. Omitted (the
  // rounds review) means all of them.
  revealedWordCount?: number
  hasPersonAlternatives: boolean
  // false while the live game hasn't revealed the alternatives yet. Omitted means always up.
  alternativesUp?: boolean
  // Rendered above the alternatives grid, inside the sliding block (the live game's timer bar).
  aboveAlternatives?: ReactNode
  // The 4 TriviumOption elements.
  alternatives: ReactNode
  // Everything `fixed` on top of the board - back button, score/stepper, result card, menus.
  // `fixed` elements aren't flex children, so they don't take part in the layout below.
  overlay?: ReactNode
}

const SLIDE_TRANSITION_MS = 450
// One whole viewport down clears the bottom edge whatever the block's own height.
const SLIDE_START = "100dvh"

// Fluid rather than one jump at `md`. The floor stays close to the flat 20px a phone used to get:
// readability isn't what should give on a tight screen, the media is.
const QUESTION_FONT_SIZE = "clamp(1.1rem, min(5vw, 6dvh), 1.75rem)"

// The screen layout shared by the live game (TriviumGame.tsx) and the finished-game review
// (TriviumRounds.tsx), so the two can't drift apart on some screen size.
//
// How the height is shared out, on any screen: the alternatives at the bottom are never shrunk
// (answering is the point), the question text is never shrunk (it has to be readable), and the
// media takes whatever is left, up to a cap - it is the one flexible piece. That's why the media
// slots are sized by the space actually remaining (flex shrink plus, for the round face, a size
// container) rather than by guesses in vh/vw: a guess is only right on the screens it was tuned
// on. The card itself sits centered in the space above the alternatives.
//
// short-wide (see index.css) flips the card into a row, media beside the question, because a short
// landscape screen has width to spare and no height; the media then fills the card's height.
export function TriviumBoard({
  media,
  questionWords,
  revealedWordCount,
  hasPersonAlternatives,
  alternativesUp = true,
  aboveAlternatives,
  alternatives,
  overlay,
}: TriviumBoardProps) {
  const visibleWords = revealedWordCount ?? questionWords.length
  const hasMedia = media.kind !== "none"

  return (
    // The top padding is the band GuardedBackButton/ScoreBadge float in: the card starts below them
    // rather than running up behind them (the owner preferred it that way). gap-4 is the minimum
    // space between the card and the timer bar once everything is packed tight.
    <div className="flex h-dvh flex-col gap-4 overflow-hidden bg-app-bg px-4 pt-16 pb-4 sm:px-6 sm:pt-20 sm:pb-6 md:px-10 md:pt-24 md:pb-10 short-wide:pt-20 short-wide:pb-3">
      {overlay}

      <div className="flex min-h-0 flex-1 flex-col justify-center">
        {/* `safe center`: in the row layout the cross axis is vertical, and centered content that
            outgrows its box spills out both ways, up under the score badge. `safe` falls back to
            start-aligned exactly then. overflow-y-auto is a last resort for the few combinations
            where even the media's floor doesn't leave room for the text - scrolling beats
            clipping. With media, short-wide makes the card fill the height so the media can too. */}
        <div
          className={`mx-auto flex min-h-0 w-full max-w-md flex-col [align-items:safe_center] gap-4 overflow-y-auto rounded-[22px] border border-line bg-surface p-4 text-center shadow-card sm:p-6 md:max-w-2xl md:rounded-3xl md:p-8 short-wide:flex-row short-wide:p-4 short-wide:text-left ${hasMedia ? "short-wide:flex-1" : ""}`}
        >
          {media.kind === "person" && (
            // A size container whose preferred height is the cap and which shrinks first when the
            // card has to give; the face inside is the largest circle that fits it.
            <div className="flex h-[min(50vw,13rem)] min-h-16 w-full shrink items-center justify-center [container-type:size] short-wide:aspect-square short-wide:h-full short-wide:w-auto short-wide:flex-none">
              <div className="size-[min(100cqw,100cqh)]">
                <PersonAvatar src={media.src} alt="" size="fill" />
              </div>
            </div>
          )}
          {media.kind === "asset" && (
            // Square at most (aspect-square takes its preferred height from its width), squashed
            // in height only when the card has to give - AssetPhoto is object-contain, so the photo
            // letterboxes instead of cropping.
            <div className="relative mx-auto aspect-square min-h-24 w-full max-w-[min(80vw,24rem)] shrink overflow-hidden rounded-2xl md:max-w-md short-wide:mx-0 short-wide:h-full short-wide:w-auto short-wide:max-w-[55%] short-wide:flex-none">
              <AssetPhoto src={media.src} alt="" onReadyChange={media.onReadyChange} />
            </div>
          )}
          {/* Every word is always laid out in its final place; only its opacity follows the reveal,
              so the text never reflows as it appears. In the row layout it has to be allowed to
              narrow, or it would push past the card's right edge. */}
          <p
            data-testid="trivium-question"
            className="min-w-0 shrink-0 text-balance break-words font-bold text-ink short-wide:shrink"
            style={{ fontSize: QUESTION_FONT_SIZE }}
          >
            {questionWords.map((segment, index) => (
              <span
                key={index}
                className={`transition-opacity duration-200 ${segment.bold ? "font-extrabold text-primary" : ""} ${index < visibleWords ? "opacity-100" : "opacity-0"}`}
              >
                {segment.word}
                {index < questionWords.length - 1 ? " " : ""}
              </span>
            ))}
          </p>
        </div>
      </div>

      <div className="mx-auto w-full max-w-md shrink-0 md:max-w-2xl">
        {/* Mounted for the whole round, not only once it's revealed: its real height is what the
            media above sizes itself against, and mounting it late would shrink the media
            mid-question. While hidden it's slid a viewport down and made invisible with a hard
            opacity switch (no fade - the slide is the only motion). The opacity also hides the
            slide back *down* on a round change, when the labels already belong to the next
            question. */}
        <div
          data-testid="trivium-alternatives"
          aria-hidden={!alternativesUp}
          className="flex w-full flex-col items-center gap-4 short-wide:gap-3"
          style={{
            transform: alternativesUp ? "translateY(0)" : `translateY(${SLIDE_START})`,
            opacity: alternativesUp ? 1 : 0,
            pointerEvents: alternativesUp ? undefined : "none",
            transition: `transform ${SLIDE_TRANSITION_MS}ms ease-out`,
          }}
        >
          {aboveAlternatives}
          {/* Person alternatives are a 2x2 grid everywhere ("cuadrantes", photo tiles); text ones
              are one column on a phone, two from `md`. short-wide lays both out in fewer rows -
              stacked rows are exactly the height it doesn't have. */}
          <div
            className={`grid w-full gap-3 md:gap-4 short-wide:gap-2 ${
              hasPersonAlternatives
                ? "grid-cols-2 short-wide:grid-cols-4"
                : "grid-cols-1 md:grid-cols-2 short-wide:grid-cols-2"
            }`}
          >
            {alternatives}
          </div>
        </div>
      </div>
    </div>
  )
}
