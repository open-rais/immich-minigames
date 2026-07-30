import type { TFunction } from "i18next"
import { useTranslation } from "react-i18next"

import type { TimelineCardOut, TimelineRoundOut } from "../../api/types"
import type { RoundsComponentProps } from "../catalog"
import { BackButton } from "../shared/BackButton"
import { EntryOptionsMenu } from "../shared/EntryOptionsMenu"
import { GameModeSubtitle } from "../shared/GameModeSubtitle"
import { ImmichLink } from "../shared/ImmichLink"
import type { TrackCard } from "./TimelineTrack"
import { TimelineTrack } from "./TimelineTrack"
import { adjustedMarkerSlot, insertCard, isTimelineRound } from "./timelineBoard"

interface Board {
  cards: TrackCard[]
  markerSlot: number | null
  isLoss: boolean
}

// Rebuilds the finished run's whole timeline client-side from GameOut.rounds - no new field, no
// new endpoint (docs/TODO/TIMELINE.md decision [H]). A round still pending an answer (a game
// reached mid-play by URL) is dropped first, same convention every other *Rounds component already
// established (ROUNDS-VIEW.md §3 H).
function buildBoard(rounds: TimelineRoundOut[], t: TFunction): Board | null {
  const answered = rounds.filter((r) => r.correct !== null)
  if (answered.length === 0) return null

  // The badge on every card is "the round whose card this was" - round 1's own board[0] (the seed
  // card) never came from anyone's guess, so it gets the special "start" badge instead of "#1".
  const initial = answered[0].board[0]
  const orderBadge = new Map<string, string>()
  orderBadge.set(initial.asset_id, t("timeline.rounds.startBadge"))
  for (const round of answered) {
    if (round.correct) orderBadge.set(round.card_asset_id, t("timeline.rounds.orderBadge", { count: round.round_index }))
  }

  const last = answered[answered.length - 1]
  const isLoss = last.correct === false

  // A perfect run (exhausted chain / max_cards, decision [F]) ends on a CORRECT last round, whose
  // card is genuinely part of the permanent board - inserted at its real slot, mirroring
  // TimelineGame.create_next_round exactly. A loss ends on a WRONG one, whose card never actually
  // joined the board, so the board here is just `last.board` as-is.
  const placedBoard: TimelineCardOut[] = isLoss
    ? last.board
    : insertCard(last.board, last.correct_slot as number, { asset_id: last.card_asset_id, date: last.card_date as string })

  const baseCards: TrackCard[] = placedBoard.map((card) => ({
    assetId: card.asset_id,
    date: card.date,
    badge: orderBadge.get(card.asset_id),
  }))

  if (!isLoss) return { cards: baseCards, markerSlot: null, isLoss: false }

  // The losing guess is shown "aparte" (decision [H]): spliced in red at the slot the player
  // actually chose, with a plain highlighted gap (no card) at the slot it really belonged at - the
  // same visual language TimelineGame.tsx's own reveal already uses for a wrong guess.
  const guessSlot = last.guess_slot as number
  const correctSlot = last.correct_slot as number
  const cards: TrackCard[] = [
    ...baseCards.slice(0, guessSlot),
    {
      assetId: last.card_asset_id,
      date: last.card_date as string,
      variant: "wrong",
      badge: t("timeline.rounds.orderBadge", { count: last.round_index }),
    },
    ...baseCards.slice(guessSlot),
  ]
  return { cards, markerSlot: adjustedMarkerSlot(correctSlot, guessSlot), isLoss: true }
}

function noop() {}

// The final timeline as a whole, not a stepper (decision [H], explicitly requested by the owner) -
// reuses TimelineTrack.tsx read-only, same fixed step as live play ([K]). "Fullscreen" layout
// (games/catalog.ts) since this owns the whole viewport itself, same as Geoguessr/Dateguessr/
// Who'sThatPerson's own rounds views.
export function TimelineRounds({ game, onBack }: RoundsComponentProps) {
  const { t } = useTranslation()
  const rounds = game.rounds.filter(isTimelineRound)
  const board = buildBoard(rounds, t)

  if (!board) return null

  const cardsWithActions: TrackCard[] = board.cards.map((card) => ({
    ...card,
    actions: (
      <EntryOptionsMenu>
        <ImmichLink kind="asset" id={card.assetId} />
      </EntryOptionsMenu>
    ),
  }))

  return (
    <div className="flex min-h-dvh w-full flex-col items-center gap-6 bg-app-bg px-6 py-10">
      <BackButton label={t("common.back")} onClick={() => onBack?.()} />

      {/* Same header shape as RoundsShell.tsx's "list" family (h1 "Rounds" -> game·mode -> final
          score) - the "fullscreen" family never shows one today, but the owner asked for Timeline's
          own board view to read consistently with the other games' end screens regardless. */}
      <div className="mt-14 text-center md:mt-0">
        <h1 className="text-3xl font-bold text-ink">{t("common.rounds.title")}</h1>
        <GameModeSubtitle gameTitle={t("timeline.title")} modeTitle={t("timeline.modes.arcade")} />
        <p className="mt-2 text-lg text-muted">{t("common.finished.finalScore", { score: game.score })}</p>
      </div>

      <div className="mx-auto max-w-md text-center">
        <p className="text-sm text-muted">{t("timeline.rounds.banner")}</p>
        {board.isLoss && <p className="mt-1 text-sm text-muted">{t("timeline.rounds.bannerLoss")}</p>}
      </div>

      <div className="flex w-full flex-1 items-center">
        <TimelineTrack
          cards={cardsWithActions}
          selectedSlot={null}
          onSelectSlot={noop}
          selectable={false}
          markerSlot={board.markerSlot}
          hideNeutralGaps
          cardSize="md"
        />
      </div>
    </div>
  )
}
