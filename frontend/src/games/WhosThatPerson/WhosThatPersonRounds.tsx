import { useState } from "react"
import { useTranslation } from "react-i18next"

import { assetThumbnailUrl } from "../../api/games"
import { GameType } from "../../api/types/common"
import type { RoundOut } from "../../api/types/common"
import type { WhosThatPersonRoundOut } from "../../api/types/whosThatPerson"
import type { RoundsComponentProps } from "../catalog"
import { AssetPhoto } from "../shared/AssetPhoto"
import { BackButton } from "../shared/BackButton"
import { EntryOptionsMenu } from "../shared/EntryOptionsMenu"
import { ImmichLink } from "../shared/ImmichLink"
import { ReportMenuItem } from "../shared/ReportMenuItem"
import { RevealResultCard } from "../shared/RevealResultCard"
import { RoundStepper } from "../rounds/RoundStepper"
import { SegmentedControl } from "../shared/SegmentedControl"
import { useRoundStepper } from "../shared/useRoundStepper"
import type { FaceBoxMode } from "./FaceBoxReadOnly"
import { FaceBoxReadOnly } from "./FaceBoxReadOnly"
import { DEFAULT_FACE_BOX_GROWTH } from "./faceBoxMath"

function isWhosThatPersonRound(round: RoundOut): round is WhosThatPersonRoundOut {
  return round.game_type === GameType.WhosThatPerson
}

// Steps through an already-finished Who'sThatPerson game's rounds, one at a time - mirrors
// GeoguessrRounds.tsx/DateguessrRounds.tsx's own "fullscreen" shape, plus the "Tu respuesta"/"Real"
// toggle FaceBoxReadOnly.tsx renders.
export function WhosThatPersonRounds({ game, onBack }: RoundsComponentProps) {
  const { t } = useTranslation()
  const [mode, setMode] = useState<FaceBoxMode>("yourAnswer")

  // A round still pending an answer (a game reached mid-play by URL) is dropped, same convention
  // every other *Rounds component already established.
  const stepper = useRoundStepper(game, isWhosThatPersonRound, (r) => r.correct !== null)

  if (!stepper) return null
  const { round, index, total, prev, next } = stepper

  const modeOptions: { value: FaceBoxMode; label: string }[] = [
    { value: "yourAnswer", label: t("whosThatPerson.rounds.yourAnswer") },
    { value: "real", label: t("whosThatPerson.rounds.real") },
  ]
  const correctCount = round.faces.filter((face) => face.correct).length

  return (
    <div className="h-dvh w-full overflow-hidden bg-app-bg">
      {/* Unlike live play's IncognitoPhoto, this is always the real, uncensored photo - the player
          already knows every answer by the time they're reviewing. */}
      <div className="fixed inset-0">
        <AssetPhoto
          key={round.id}
          src={assetThumbnailUrl(round.asset_id)}
          alt=""
          overlay={
            <>
              {round.faces.map((face) => (
                <FaceBoxReadOnly
                  key={face.face_id}
                  face={face}
                  mode={mode}
                  growthFactor={game.face_box_growth ?? DEFAULT_FACE_BOX_GROWTH}
                />
              ))}
            </>
          }
        />
      </div>

      <BackButton label={t("common.back")} onClick={() => onBack?.()} />
      <RoundStepper current={index + 1} total={total} onPrev={prev} onNext={next} />
      {/* Its own row below the stepper rather than crammed onto the same line as it (the doc's
          mockup draws them side by side) - on a narrow phone that'd be four fixed elements
          (back/stepper/toggle/options-menu) fighting over one row's width. */}
      <div className="fixed top-16 left-1/2 z-30 w-44 -translate-x-1/2 md:top-20">
        <SegmentedControl options={modeOptions} value={mode} onChange={setMode} />
      </div>

      <div className="fixed top-[18px] right-[18px] z-30 md:top-7 md:right-10">
        <EntryOptionsMenu>
          <ImmichLink kind="asset" id={round.asset_id} />
          <ReportMenuItem kind="asset" id={round.asset_id} />
        </EntryOptionsMenu>
      </div>

      {round.score_delta !== null && (
        <RevealResultCard
          positionClassName="bottom-[18px] left-[18px] md:bottom-7 md:left-10"
          scoreDelta={round.score_delta}
          subtitle={t("whosThatPerson.result.correctCount", {
            correct: correctCount,
            total: round.faces.length,
          })}
        />
      )}
    </div>
  )
}
