import { useEffect, useRef } from "react"
import { useTranslation } from "react-i18next"

import type { TimelineCardVariant } from "./TimelineCard"
import { TimelineCard } from "./TimelineCard"

// The strip is a plain scrollable list, NOT a proportional timeline ruler (docs/TODO/TIMELINE.md
// decision [K]): fixed card width and fixed gap between every pair of cards, no matter how far
// apart their real dates are. Nothing here reuses Dateguessr/TimelineRuler.tsx or any of its
// scale/zoom math.
const TRACK_GAP_CLASS = "gap-2.5 md:gap-3.5"
// Every gap button is the same size regardless of position - the two extremes included - so no
// slot is an easier or harder tap target than another. Matches TimelineCard's "sm" card height so
// the row stays visually aligned.
const GAP_SIZE_CLASS = "h-[104px] w-11 md:h-32 md:w-12"

export interface TrackCard {
  assetId: string
  date: string | null
  variant?: TimelineCardVariant
  // false while this card's slot is reserved for layout/measurement but not yet meant to be seen -
  // the fly-in animation target in TimelineGame.tsx renders it invisible for one frame so its final
  // position can be measured before the floating "big card" animates toward it.
  visible?: boolean
}

export type TrackSlotKind = "gap" | "card"

interface TimelineTrackProps {
  cards: TrackCard[]
  selectedSlot: number | null
  onSelectSlot: (slot: number) => void
  selectable: boolean
  // Extra highlighted gap with no card in it - the real insertion point on a missed guess
  // (docs/TODO/TIMELINE.md §5.2's "hueco correcto en verde").
  markerSlot?: number | null
  registerSlotRef?: (kind: TrackSlotKind, index: number, el: HTMLDivElement | null) => void
  // Bumped by the caller whenever focusTarget should be scrolled into view again, even if the
  // target itself didn't change (e.g. re-focusing the same slot after a resize).
  focusToken?: number
  focusTarget?: { kind: TrackSlotKind; index: number } | null
}

export function TimelineTrack({
  cards,
  selectedSlot,
  onSelectSlot,
  selectable,
  markerSlot = null,
  registerSlotRef,
  focusToken,
  focusTarget,
}: TimelineTrackProps) {
  const { t } = useTranslation()
  const elementsRef = useRef<Map<string, HTMLDivElement>>(new Map())

  useEffect(() => {
    if (!focusTarget) return
    const el = elementsRef.current.get(`${focusTarget.kind}-${focusTarget.index}`)
    el?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" })
    // focusToken is the re-run trigger, not a value read inside the effect.
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [focusToken])

  function setRef(kind: TrackSlotKind, index: number, el: HTMLDivElement | null) {
    const key = `${kind}-${index}`
    if (el) elementsRef.current.set(key, el)
    else elementsRef.current.delete(key)
    registerSlotRef?.(kind, index, el)
  }

  return (
    <div className={`flex w-full items-center overflow-x-auto px-4 py-3 [scrollbar-width:thin] md:px-8 ${TRACK_GAP_CLASS}`}>
      {Array.from({ length: cards.length + 1 }, (_, gapIndex) => gapIndex).map((gapIndex) => (
        <div key={`slot-${gapIndex}`} className="flex flex-none items-center">
          <div ref={(el) => setRef("gap", gapIndex, el)} className={`flex flex-none items-center justify-center ${GAP_SIZE_CLASS}`}>
            <button
              type="button"
              aria-label={t("timeline.selectSlotAria")}
              disabled={!selectable}
              onClick={() => onSelectSlot(gapIndex)}
              className="flex h-full w-full items-center justify-center disabled:cursor-default"
            >
              <span
                className={`h-3 w-3 rounded-full border-2 transition-colors ${
                  selectedSlot === gapIndex
                    ? "border-primary bg-primary"
                    : markerSlot === gapIndex
                      ? "border-emerald-500 bg-emerald-500"
                      : "border-line-strong bg-transparent"
                }`}
              />
            </button>
          </div>
          {cards[gapIndex] && (
            <div
              ref={(el) => setRef("card", gapIndex, el)}
              className={cards[gapIndex].visible === false ? "opacity-0" : ""}
            >
              <TimelineCard
                assetId={cards[gapIndex].assetId}
                date={cards[gapIndex].date}
                size="sm"
                variant={cards[gapIndex].variant ?? "default"}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
