import { GameType } from "../../api/types/common"
import type { RoundOut } from "../../api/types/common"
import type { TimelineCardOut, TimelineRoundOut } from "../../api/types/timeline"
import type { TrackCard } from "./TimelineTrack"

// Small pure helpers shared between TimelineGame.tsx (live play) and TimelineRounds.tsx (roadmap
// #10's "Ver rondas") - both need the same board bookkeeping, so this lives once inside the
// Timeline package instead of being copy-pasted (docs/TODO/DECOUPLING.md decision [J] is about not
// sharing logic with OTHER games, not about this).

// This component/module only ever handles "timeline" rounds, so a mismatched game_type means the
// backend returned something unexpected.
export function isTimelineRound(round: RoundOut): round is TimelineRoundOut {
  return round.game_type === GameType.Timeline
}

export function toTrackCard(card: TimelineCardOut): TrackCard {
  return { assetId: card.asset_id, date: card.date }
}

export function insertCard(
  board: TimelineCardOut[],
  slot: number,
  card: TimelineCardOut,
): TimelineCardOut[] {
  return [...board.slice(0, slot), card, ...board.slice(slot)]
}

// Where a wrong guess's real insertion point lands once the track also shows the (also wrong)
// guessed card spliced in at guessSlot - every original gap index at or after guessSlot shifts
// right by one slot to make room for it. correctSlot is always != guessSlot here: accepted_slots
// always contains correctSlot (docs/TODO/TIMELINE.md decision [D]), so a rejected guess can't be it.
export function adjustedMarkerSlot(correctSlot: number, guessSlot: number): number {
  return correctSlot < guessSlot ? correctSlot : correctSlot + 1
}
