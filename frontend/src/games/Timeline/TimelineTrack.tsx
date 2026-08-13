import type { ReactNode } from "react"
import { useEffect, useRef } from "react"
import { useTranslation } from "react-i18next"

import type { TimelineCardSize, TimelineCardVariant } from "./TimelineCard"
import { TimelineCard } from "./TimelineCard"

// The strip is a plain scrollable list, NOT a proportional timeline ruler: fixed card width and
// fixed gap between every pair of cards, no matter how far
// apart their real dates are. Nothing here reuses Dateguessr/TimelineRuler.tsx or any of its
// scale/zoom math.
const TRACK_GAP_CLASS = "gap-2.5 md:gap-3.5"
// Every gap's height matches the track's own card size (TimelineCard.tsx's SIZE_CLASS) so the row
// stays visually aligned.
const GAP_HEIGHT_CLASS: Record<"sm" | "md", string> = {
  sm: "h-40 md:h-44",
  md: "h-64 md:h-72",
}
// Full width: every gap is the same size regardless of position - the two extremes included - so
// no slot is an easier or harder tap target than another, and deliberately generous (well past the
// ~44px minimum touch target) since this is the primary way to place a guess in live play.
const GAP_FULL_WIDTH_CLASS: Record<"sm" | "md", string> = {
  sm: "w-14 md:w-16",
  md: "w-16 md:w-20",
}
// "Ver rondas" only - a gap with no marker in it (hideNeutralGaps) has nothing to show, so it
// shrinks to a thin breathing gap between its two neighboring cards instead of reserving a full
// tap-target's worth of empty space (only the live-play "every slot is a real tap target" gap needs
// GAP_FULL_WIDTH_CLASS's generous width).
const GAP_NEUTRAL_WIDTH_CLASS = "w-2 md:w-3"
const GAP_MARKER_CLASS = "h-9 w-9 rounded-xl md:h-10 md:w-10"

export interface TrackCard {
  assetId: string
  date: string | null
  variant?: TimelineCardVariant
  // false while this card's slot is reserved for layout/measurement but not yet meant to be seen -
  // the fly-in animation target in TimelineGame.tsx renders it invisible for one frame so its final
  // position can be measured before the floating "big card" animates toward it.
  visible?: boolean
  // "Ver rondas" only - forwarded straight to TimelineCard's own badge/actions props.
  badge?: string
  actions?: ReactNode
}

export type TrackSlotKind = "gap" | "card"

interface TimelineTrackProps {
  cards: TrackCard[]
  selectedSlot: number | null
  onSelectSlot: (slot: number) => void
  selectable: boolean
  // Extra highlighted gap with no card in it - the real insertion point on a missed guess.
  markerSlot?: number | null
  // "Ver rondas" only - every other (non-marker, non-selected) gap renders as empty space instead
  // of its neutral bordered square, since there's nothing to pick in a read-only board.
  hideNeutralGaps?: boolean
  // Live play uses "sm" (compact, alongside the big card); "Ver rondas" uses "md" (the whole
  // viewport is the board, so cards can afford to be bigger).
  cardSize?: "sm" | "md"
  registerSlotRef?: (kind: TrackSlotKind, index: number, el: HTMLDivElement | null) => void
  // Bumped by the caller whenever focusTarget should be scrolled into view again, even if the
  // target itself didn't change (e.g. re-focusing the same slot after a resize).
  focusToken?: number
  focusTarget?: { kind: TrackSlotKind; index: number } | null
  // Live play only (TimelineGame.tsx) - opens a full-photo modal for an already-placed card.
  // Undefined in "Ver rondas" (TimelineRounds.tsx already has its own per-card actions menu).
  onCardClick?: (assetId: string) => void
}

export function TimelineTrack({
  cards,
  selectedSlot,
  onSelectSlot,
  selectable,
  markerSlot = null,
  hideNeutralGaps = false,
  cardSize = "sm",
  registerSlotRef,
  focusToken,
  focusTarget,
  onCardClick,
}: TimelineTrackProps) {
  const { t } = useTranslation()
  const elementsRef = useRef<Map<string, HTMLDivElement>>(new Map())

  useEffect(() => {
    if (!focusTarget) return
    const el = elementsRef.current.get(`${focusTarget.kind}-${focusTarget.index}`)
    el?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" })
    // focusToken is the re-run trigger, not a value read inside the effect.
    // oxlint-disable-next-line
  }, [focusToken])

  function setRef(kind: TrackSlotKind, index: number, el: HTMLDivElement | null) {
    const key = `${kind}-${index}`
    if (el) elementsRef.current.set(key, el)
    else elementsRef.current.delete(key)
    registerSlotRef?.(kind, index, el)
  }

  return (
    <div
      className={`flex w-full items-center overflow-x-auto px-4 py-3 [scrollbar-width:thin] md:px-8 ${TRACK_GAP_CLASS}`}
    >
      {Array.from({ length: cards.length + 1 }, (_, gapIndex) => gapIndex).map((gapIndex) => {
        const highlighted = selectedSlot === gapIndex || markerSlot === gapIndex
        const gapWidthClass =
          hideNeutralGaps && !highlighted ? GAP_NEUTRAL_WIDTH_CLASS : GAP_FULL_WIDTH_CLASS[cardSize]
        return (
          <div key={`slot-${gapIndex}`} className="flex flex-none items-center">
            <div
              ref={(el) => setRef("gap", gapIndex, el)}
              className={`flex flex-none items-center justify-center ${GAP_HEIGHT_CLASS[cardSize]} ${gapWidthClass}`}
            >
              <button
                type="button"
                aria-label={t("timeline.selectSlotAria")}
                disabled={!selectable}
                onClick={() => onSelectSlot(gapIndex)}
                className="flex h-full w-full items-center justify-center disabled:cursor-default"
              >
                {(highlighted || !hideNeutralGaps) && (
                  <span
                    className={`${GAP_MARKER_CLASS} border-2 transition-colors ${
                      selectedSlot === gapIndex
                        ? "border-primary bg-primary/20"
                        : markerSlot === gapIndex
                          ? "border-emerald-500 bg-emerald-500/20"
                          : "border-line-strong bg-transparent"
                    }`}
                  />
                )}
              </button>
            </div>
            {cards[gapIndex] && (
              <div
                ref={(el) => setRef("card", gapIndex, el)}
                className={cards[gapIndex].visible === false ? "opacity-0" : ""}
              >
                <TimelineCard
                  key={cards[gapIndex].assetId}
                  assetId={cards[gapIndex].assetId}
                  date={cards[gapIndex].date}
                  size={cardSize as TimelineCardSize}
                  variant={cards[gapIndex].variant ?? "default"}
                  badge={cards[gapIndex].badge}
                  actions={cards[gapIndex].actions}
                  onClick={onCardClick ? () => onCardClick(cards[gapIndex].assetId) : undefined}
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
