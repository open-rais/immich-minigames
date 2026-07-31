import { useTranslation } from "react-i18next"

import { GameType } from "../../api/types/common"
import type { RoundOut } from "../../api/types/common"
import type { DateguessrRoundOut } from "../../api/types/dateguessr"
import type { RoundsComponentProps } from "../catalog"
import { AssetCarousel } from "../shared/AssetCarousel"
import { BackButton } from "../shared/BackButton"
import { EntryOptionsMenu } from "../shared/EntryOptionsMenu"
import { ImmichLink } from "../shared/ImmichLink"
import { RevealResultCard } from "../shared/RevealResultCard"
import { RoundStepper } from "../rounds/RoundStepper"
import { useRoundStepper } from "../shared/useRoundStepper"
import { ABOVE_RULER_BOTTOM_CLASS, RULER_BOTTOM_CLASS, TimelineRuler } from "./TimelineRuler"

function isDateguessrRound(round: RoundOut): round is DateguessrRoundOut {
  return round.game_type === GameType.Dateguessr
}

// TimelineRuler's onSelectedChange is a required prop even in read-only review - every round here
// is `disabled`, so it's never actually invoked.
function noop() {}

// Steps through an already-finished Dateguessr game's rounds, one at a time, exactly as they
// looked right after their reveal (ROUNDS-VIEW.md roadmap #10) - mirrors DateguessrGame.tsx's own
// finished-round layout, but with the stepper's prev/next arrows in place of a live game.
export function DateguessrRounds({ game, onBack }: RoundsComponentProps) {
  const { t } = useTranslation()

  // actual_date never got set on a round still pending an answer (a game reached mid-play by URL)
  // - same convention MoreOrLessRounds.tsx already established for its own redacted-field check
  // (§3 H): there's nothing to reveal for it.
  const stepper = useRoundStepper(game, isDateguessrRound, (r) => r.actual_date !== null)

  if (!stepper) return null
  const { round, index, total, prev, next } = stepper

  return (
    <div className="h-dvh w-full overflow-hidden bg-app-bg">
      <div className={`fixed inset-0 ${RULER_BOTTOM_CLASS} overflow-hidden`}>
        <AssetCarousel key={round.id} assetIds={round.asset_ids} alt={t("dateguessr.title")} />
      </div>

      <BackButton label={t("common.back")} onClick={() => onBack?.()} />
      <RoundStepper current={index + 1} total={total} onPrev={prev} onNext={next} />

      <div className="fixed top-[18px] right-[18px] z-30 md:top-7 md:right-10">
        <EntryOptionsMenu>
          <ImmichLink kind="asset" id={round.asset_ids[0]} />
        </EntryOptionsMenu>
      </div>

      {/* key={round.id} remounts the ruler fresh on every stepper navigation, so its own pan/zoom
          reveal animation replays instead of tweening between two unrelated rounds' dates (§5 of
          the doc, same reasoning as GeoguessrRounds.tsx's MapPicker). */}
      <TimelineRuler
        key={round.id}
        selected={round.guess_date}
        onSelectedChange={noop}
        actual={round.actual_date}
        disabled
        showZoomControls={false}
      />

      {round.days_off !== null && round.score_delta !== null && (
        <RevealResultCard
          positionClassName={`${ABOVE_RULER_BOTTOM_CLASS} left-[18px] md:left-10`}
          scoreDelta={round.score_delta}
          subtitle={t("dateguessr.result.daysOff", { count: round.days_off })}
        />
      )}
    </div>
  )
}
