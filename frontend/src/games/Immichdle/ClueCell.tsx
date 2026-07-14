import { useTranslation } from "react-i18next"

import type { ClueResult } from "./clueColors"

const variantClass: Record<ClueResult["variant"], string> = {
  match: "bg-clue-match",
  close: "bg-clue-close",
  miss: "bg-clue-miss",
}

// The "?"/arrow reads as a big translucent watermark filling the tile (smashdle's look), with the
// actual value (date/count) as smaller solid text in front - rather than a small inline icon next
// to the text, which is how every other icon in this app (Button, BackButton) is normally used.
// Same stroke-icon family for all three glyphs (arrow-up/arrow-down/question) - same viewBox,
// stroke width and rounded caps - so the "?" reads as part of the same icon set instead of a
// mismatched bold text character next to line-art arrows.
function BackgroundGlyph({ background }: { background: ClueResult["background"] }) {
  if (!background) return null
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="absolute inset-0 h-full w-full p-2 text-white/25"
    >
      {background === "up" && <path d="M12 19V5M5 12l7-7 7 7" />}
      {background === "down" && <path d="M12 5v14M5 12l7 7 7-7" />}
      {background === "question" && (
        <>
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </>
      )}
    </svg>
  )
}

// One clue's tile - always square, a solid Wordle-style fill (unlike the rest of the app's cards/
// badges, which pair a light tint with dark saturated text) since this is the one place the app
// shows a 3-way match/close/miss verdict at a glance. No label here - GuessTable renders the column
// labels once, in a header row, instead of repeating them on every tile.
export function ClueCell({ clue }: { clue: ClueResult }) {
  const { i18n } = useTranslation()

  const text =
    clue.kind === "text"
      ? String(clue.value)
      : clue.kind === "percent"
        ? `${clue.value}%`
        : clue.kind === "date"
          ? new Intl.DateTimeFormat(i18n.language, { year: "2-digit", month: "short", day: "numeric" }).format(new Date(clue.value!))
          : String(clue.value)

  return (
    <div className={`relative flex aspect-square w-full items-center justify-center overflow-hidden rounded-xl ${variantClass[clue.variant]}`}>
      <BackgroundGlyph background={clue.background} />
      <span className="relative z-10 px-1 text-center font-mono text-sm leading-tight font-bold text-white md:px-2 md:text-lg">{text}</span>
    </div>
  )
}
