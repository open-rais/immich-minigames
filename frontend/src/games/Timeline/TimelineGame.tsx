import type { TransitionEvent } from "react"
import { useLayoutEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { assetThumbnailUrl, playRound } from "../../api/games"
import { GameType, Mode } from "../../api/types/common"
import type { TimelineRoundOut } from "../../api/types/timeline"
import type { GameComponentProps } from "../catalog"
import { AssetPhoto } from "../shared/AssetPhoto"
import { Button } from "../shared/Button"
import { ErrorScreen, FinishedScreen, IdleScreen } from "../shared/GameScreens"
import { GuardedBackButton } from "../shared/GuardedBackButton"
import { RevealResultCard } from "../shared/RevealResultCard"
import { ScoreBadge } from "../shared/ScoreBadge"
import { useRoundGame } from "../shared/useRoundGame"
import { PlacedCardModal } from "./PlacedCardModal"
import type { TrackCard, TrackSlotKind } from "./TimelineTrack"
import { TimelineTrack } from "./TimelineTrack"
import { adjustedMarkerSlot, isTimelineRound, toTrackCard } from "./timelineBoard"

const GAME_TYPE = GameType.Timeline
const MODE = Mode.Arcade
const REVEAL_HOLD_MS = 2200
const FLY_TRANSITION_MS = 500

// The strip pinned to the bottom of the screen (TimelineTrack.tsx) and the amount of space
// reserved above it for the big card - one h-*/bottom-* pair per breakpoint, kept next to each
// other so a height change is a single edit (same "pixel coupling" convention as Dateguessr/
// TimelineRuler.tsx's RULER_HEIGHT_CLASS/RULER_BOTTOM_CLASS, though nothing here reuses that file).
// Sized to TimelineCard.tsx's "sm" card height (SIZE_CLASS.sm: h-40/md:h-44) plus
// TimelineTrack.tsx's own py-3 (12px top+bottom) and a couple px of rounding safety - not a
// round Tailwind step, to avoid leaving visible empty space below the cards. Resize together when
// the card size changes.
const TRACK_HEIGHT_CLASS = "h-[186px] md:h-[202px]"
const TRACK_BOTTOM_CLASS = "bottom-[186px] md:bottom-[202px]"
// Track height + a breathing gap - for the confirm button / reveal card floating just above it.
const ABOVE_TRACK_BOTTOM_CLASS = "bottom-[198px] md:bottom-[218px]"

// Ring shown once the card has "become a card" (see its render site below) and the guess is
// known - no ring while it's still just a plain photo, and none while correct/wrong isn't known
// yet either.
const BIG_CARD_RING_CLASS: Record<"default" | "correct" | "wrong", string> = {
  default: "",
  correct: "ring-4 ring-emerald-500",
  wrong: "ring-4 ring-rose-500",
}

export function TimelineGame({ coverUrl, hasRoundsView, daily = false }: GameComponentProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  const [selectedSlot, setSelectedSlot] = useState<number | null>(null)
  // Full-photo view for a tap on an already-placed track card (PlacedCardModal, rendered below).
  const [viewingAssetId, setViewingAssetId] = useState<string | null>(null)

  // Reveal fly-in animation: the big card animates toward the track slot the player guessed, its
  // offset measured for real via getBoundingClientRect (never a fixed pixel constant - the same
  // limitation ROADMAP.md documents for MoreOrLess's slide). flyReady gates the CSS transition so
  // the very first paint after measuring still shows the identity transform, then a rAF flips it to
  // the computed target - transitionEnabled/revealDone mirror MoreOrLessGame.tsx's own
  // transitionEnabled toggle so resetting for the next round never itself animates.
  // A single uniform scale, not independent scaleX/scaleY - the "from" box (fullscreen) and the
  // "to" box (a small track card) don't share an aspect ratio, and a non-uniform CSS transform
  // scale stretches whatever's inside it. A uniform scale just shrinks the photo without
  // distorting it (the same "fit, don't stretch" AssetPhoto's own object-contain already does),
  // landing it flush with the target on its longer axis and slightly short on the other - fine,
  // since the flying box's opacity drops to 0 the instant it finishes, handing off to the real
  // TimelineCard underneath.
  const [flyTransform, setFlyTransform] = useState<{
    dx: number
    dy: number
    scale: number
  } | null>(null)
  const [flyReady, setFlyReady] = useState(false)
  const [transitionEnabled, setTransitionEnabled] = useState(true)
  const [revealDone, setRevealDone] = useState(false)
  const [focusTarget, setFocusTarget] = useState<{ kind: TrackSlotKind; index: number } | null>(
    null,
  )
  const [focusToken, setFocusToken] = useState(0)

  const bigCardRef = useRef<HTMLDivElement>(null)
  const cardSlotRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  const {
    screen,
    busy,
    game,
    round,
    phase,
    revealed,
    hasCurrentGame,
    startGame,
    resumeGame,
    submitGuess,
    backToIdle,
  } = useRoundGame<TimelineRoundOut, number>({
    gameType: GAME_TYPE,
    mode: MODE,
    revealHoldMs: REVEAL_HOLD_MS,
    isRound: isTimelineRound,
    playRound: (gameId, roundId, guess) => playRound(gameId, roundId, { slot: guess }),
    onNewRound: () => {
      setSelectedSlot(null)
      setFlyTransform(null)
      setFlyReady(false)
      setRevealDone(false)
      setFocusTarget(null)
      setTransitionEnabled(false)
    },
    daily,
  })

  // Measures the fly-in target as soon as a guess is revealed - see the state comment above.
  // Depends only on the identity of the round being revealed, not its fields (re-measuring on every
  // field change of the same round would restart the animation).
  useLayoutEffect(() => {
    if (phase !== "revealed" || !round || round.guess_slot === null) return
    const bigEl = bigCardRef.current
    const targetEl = cardSlotRefs.current.get(round.guess_slot)
    if (!bigEl || !targetEl) {
      setRevealDone(true)
      return
    }
    const fromRect = bigEl.getBoundingClientRect()
    const toRect = targetEl.getBoundingClientRect()
    setFlyTransform({
      dx: toRect.left + toRect.width / 2 - (fromRect.left + fromRect.width / 2),
      dy: toRect.top + toRect.height / 2 - (fromRect.top + fromRect.height / 2),
      scale: Math.min(toRect.width / fromRect.width, toRect.height / fromRect.height),
    })
    const raf = requestAnimationFrame(() => setFlyReady(true))
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line
  }, [phase, round?.id])

  // Re-enables the transition one frame after it was turned off for an instant reset (onNewRound) -
  // identical pattern to MoreOrLessGame.tsx's own transitionEnabled effect.
  useLayoutEffect(() => {
    if (transitionEnabled) return
    const raf = requestAnimationFrame(() => setTransitionEnabled(true))
    return () => cancelAnimationFrame(raf)
  }, [transitionEnabled])

  function handleFlyTransitionEnd(e: TransitionEvent<HTMLDivElement>) {
    if (e.target !== e.currentTarget || e.propertyName !== "transform" || !flyReady) return
    setRevealDone(true)
    if (!round || round.guess_slot === null) return
    if (round.correct) {
      setFocusTarget({ kind: "card", index: round.guess_slot })
    } else if (round.correct_slot !== null) {
      setFocusTarget({
        kind: "gap",
        index: adjustedMarkerSlot(round.correct_slot, round.guess_slot),
      })
    }
    setFocusToken((n) => n + 1)
  }

  function registerSlotRef(kind: TrackSlotKind, index: number, el: HTMLDivElement | null) {
    if (kind !== "card") return
    if (el) cardSlotRefs.current.set(index, el)
    else cardSlotRefs.current.delete(index)
  }

  // Daily's "already played today" check (useGameSession's idle effect) resolves async -
  // hasCurrentGame stays null until it does, so this avoids a beat of the idle/start screen before
  // screen flips to "finished".
  if (daily && hasCurrentGame === null) return <div className="min-h-dvh bg-app-bg" />

  if (screen === "idle") {
    return (
      <IdleScreen
        title={t("timeline.title")}
        modeTitle={t("timeline.modes.arcade")}
        description={t("timeline.start.description")}
        coverUrl={coverUrl}
        onStart={startGame}
        onBack={backToMenu}
        busy={busy}
        hasCurrentGame={hasCurrentGame}
        onContinue={resumeGame}
        allowNewGame={!daily}
      />
    )
  }

  if (screen === "error") {
    return <ErrorScreen onRetry={startGame} onBack={backToMenu} busy={busy} />
  }

  if (screen === "finished") {
    return (
      <FinishedScreen
        score={game?.score ?? 0}
        onPlayAgain={startGame}
        onBack={backToMenu}
        busy={busy}
        gameId={game?.id}
        hasRoundsView={hasRoundsView}
        allowPlayAgain={!daily}
        dailyShare={
          daily && game
            ? {
                gameId: game.id,
                gameType: GAME_TYPE,
                mode: MODE,
                gameTitle: t("timeline.title"),
                modeTitle: t("timeline.modes.arcade"),
              }
            : undefined
        }
      />
    )
  }

  if (!game || !round) return null

  const displayCards: TrackCard[] =
    phase === "revealed" && round.guess_slot !== null && round.card_date !== null
      ? [
          ...round.board.slice(0, round.guess_slot).map(toTrackCard),
          {
            assetId: round.card_asset_id,
            date: round.card_date,
            variant: round.correct ? "correct" : "wrong",
            visible: revealDone,
          },
          ...round.board.slice(round.guess_slot).map(toTrackCard),
        ]
      : round.board.map(toTrackCard)

  const markerSlot =
    phase === "revealed" &&
    round.correct === false &&
    round.correct_slot !== null &&
    round.guess_slot !== null
      ? adjustedMarkerSlot(round.correct_slot, round.guess_slot)
      : null

  const bigCardTransform =
    flyReady && flyTransform
      ? `translate(${flyTransform.dx}px, ${flyTransform.dy}px) scale(${flyTransform.scale})`
      : "translate(0px, 0px) scale(1)"

  return (
    <div className="relative h-dvh w-full overflow-hidden bg-app-bg">
      {/* Fullscreen photo while guessing - same "fixed inset-0 down to the controls below it"
          sizing Geoguessr/Dateguessr use for their own AssetCarousel, not a small boxed-in card
          (the roadmap's own complaint: it should look like a photo here, not a cropped card). Once
          submitted (phase leaves "guessing"), it "becomes a card" - rounded corners + a
          correct/wrong ring appear, and the same element scales/translates itself down into its
          track slot via bigCardTransform below - the DOM box itself never changes size, only its
          CSS transform, so the big-photo-to-small-card shrink is what the fly animation IS. */}
      <div
        ref={bigCardRef}
        className={`fixed inset-0 z-30 ${TRACK_BOTTOM_CLASS}`}
        style={{
          transform: bigCardTransform,
          transition: transitionEnabled ? `transform ${FLY_TRANSITION_MS}ms ease-out` : "none",
          opacity: revealDone ? 0 : 1,
        }}
        onTransitionEnd={handleFlyTransitionEnd}
      >
        {/* key forces a full remount per round so a previous round's zoom/pan doesn't carry over. */}
        <div
          key={round.card_asset_id}
          className={`relative h-full w-full overflow-hidden transition-[border-radius,box-shadow] ${
            phase === "guessing"
              ? ""
              : `rounded-2xl ${
                  BIG_CARD_RING_CLASS[
                    round.correct === true
                      ? "correct"
                      : round.correct === false
                        ? "wrong"
                        : "default"
                  ]
                }`
          }`}
        >
          <AssetPhoto src={assetThumbnailUrl(round.card_asset_id)} alt="" />
        </div>
      </div>

      <GuardedBackButton onExit={backToIdle} />
      <ScoreBadge label={t("common.score")} score={game.score} />

      {phase === "guessing" && (
        <div className={`fixed ${ABOVE_TRACK_BOTTOM_CLASS} left-[18px] z-30 md:left-10`}>
          <Button
            variant="primary"
            className="px-6 py-3 shadow-card"
            onClick={() => selectedSlot !== null && submitGuess(selectedSlot)}
            disabled={selectedSlot === null || busy}
          >
            {t("timeline.confirmSlot")}
          </Button>
        </div>
      )}

      {revealed && round.score_delta !== null && (
        <RevealResultCard
          positionClassName={`${ABOVE_TRACK_BOTTOM_CLASS} left-[18px] md:left-10`}
          scoreDelta={round.score_delta}
          subtitle={t(round.correct ? "timeline.result.correct" : "timeline.result.wrong")}
        />
      )}

      <div
        className={`fixed inset-x-0 bottom-0 z-20 flex flex-col border-t border-line bg-surface shadow-card ${TRACK_HEIGHT_CLASS}`}
      >
        <TimelineTrack
          cards={displayCards}
          selectedSlot={selectedSlot}
          onSelectSlot={setSelectedSlot}
          selectable={phase === "guessing"}
          markerSlot={markerSlot}
          registerSlotRef={registerSlotRef}
          focusToken={focusToken}
          focusTarget={focusTarget}
          onCardClick={setViewingAssetId}
        />
      </div>

      {viewingAssetId && (
        <PlacedCardModal assetId={viewingAssetId} onClose={() => setViewingAssetId(null)} />
      )}
    </div>
  )
}
