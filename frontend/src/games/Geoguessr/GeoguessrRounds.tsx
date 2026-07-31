import { useTranslation } from "react-i18next"

import { GameType } from "../../api/types/common"
import type { RoundOut } from "../../api/types/common"
import type { GeoguessrRoundOut } from "../../api/types/geoguessr"
import type { RoundsComponentProps } from "../catalog"
import { AssetCarousel } from "../shared/AssetCarousel"
import { BackButton } from "../shared/BackButton"
import { EntryOptionsMenu } from "../shared/EntryOptionsMenu"
import { ImmichLink } from "../shared/ImmichLink"
import { RevealResultCard } from "../shared/RevealResultCard"
import { RoundStepper } from "../rounds/RoundStepper"
import { useRoundStepper } from "../shared/useRoundStepper"
import { MapPicker } from "./MapPicker"

function isGeoguessrRound(round: RoundOut): round is GeoguessrRoundOut {
  return round.game_type === GameType.Geoguessr
}

// MapPicker's onPinChange is a required prop even in read-only review - every round here is
// `disabled`, so it's never actually invoked.
function noop() {}

// Steps through an already-finished Geoguessr game's rounds, one at a time, exactly as they looked
// right after their reveal - mirrors GeoguessrGame.tsx's own
// finished-round layout, but with the stepper's prev/next arrows in place of a live game.
export function GeoguessrRounds({ game, onBack }: RoundsComponentProps) {
  const { t } = useTranslation()

  // actual_latitude never got set on a round still pending an answer (a game reached mid-play by
  // URL) - same convention MoreOrLessRounds.tsx already established for its own redacted-field
  // check: there's nothing to reveal for it.
  const stepper = useRoundStepper(game, isGeoguessrRound, (r) => r.actual_latitude !== null)

  if (!stepper) return null
  const { round, index, total, prev, next } = stepper

  const pin =
    round.guess_latitude !== null && round.guess_longitude !== null
      ? { lat: round.guess_latitude, lng: round.guess_longitude }
      : null
  const actual =
    round.actual_latitude !== null && round.actual_longitude !== null
      ? { lat: round.actual_latitude, lng: round.actual_longitude }
      : null

  return (
    <div className="h-dvh w-full overflow-hidden bg-app-bg">
      <div className="fixed inset-0">
        <AssetCarousel key={round.id} assetIds={round.asset_ids} alt={t("geoguessr.title")} />
      </div>

      <BackButton label={t("common.back")} onClick={() => onBack?.()} />
      <RoundStepper current={index + 1} total={total} onPrev={prev} onNext={next} />

      <div className="fixed top-[18px] right-[18px] z-30 md:top-7 md:right-10">
        <EntryOptionsMenu>
          <ImmichLink kind="asset" id={round.asset_ids[0]} />
        </EntryOptionsMenu>
      </div>

      {/* No forceExpanded - collapsed-by-default, hover(desktop)/tap(mobile)-to-expand, exactly
          like real gameplay's own reveal state. Forcing it open always would permanently cover the
          asset carousel underneath, with no way to browse the round's other photos. key={round.id}
          remounts the map fresh on every stepper navigation, so its own fitBounds reveal animation
          replays instead of tweening between two unrelated rounds' coordinates. */}
      <MapPicker key={round.id} pin={pin} onPinChange={noop} actual={actual} disabled />

      {round.distance_km !== null && round.score_delta !== null && (
        <RevealResultCard
          positionClassName="bottom-[18px] left-[18px] md:bottom-7 md:left-10"
          scoreDelta={round.score_delta}
          subtitle={t("geoguessr.result.distance", { distance: round.distance_km.toFixed(1) })}
        />
      )}
    </div>
  )
}
