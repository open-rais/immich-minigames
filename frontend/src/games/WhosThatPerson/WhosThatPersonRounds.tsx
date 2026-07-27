import { useState } from "react"
import { useTranslation } from "react-i18next"

import { assetThumbnailUrl } from "../../api/games"
import { GameType } from "../../api/types"
import type { WhosThatPersonRoundOut } from "../../api/types"
import type { RoundsComponentProps } from "../catalog"
import { AssetPhoto } from "../shared/AssetPhoto"
import { BackButton } from "../shared/BackButton"
import { EntryOptionsMenu } from "../shared/EntryOptionsMenu"
import { ImmichLink } from "../shared/ImmichLink"
import { RevealResultCard } from "../shared/RevealResultCard"
import { RoundStepper } from "../rounds/RoundStepper"
import { SegmentedControl } from "../shared/SegmentedControl"
import type { FaceBoxMode } from "./FaceBoxReadOnly"
import { FaceBoxReadOnly } from "./FaceBoxReadOnly"

// Steps through an already-finished Who'sThatPerson game's rounds, one at a time (ROUNDS-VIEW.md
// roadmap #10) - mirrors GeoguessrRounds.tsx/DateguessrRounds.tsx's own "fullscreen" shape, plus the
// "Tu respuesta"/"Real" toggle (§4.6) FaceBoxReadOnly.tsx renders.
export function WhosThatPersonRounds({ game, onBack }: RoundsComponentProps) {
  const { t } = useTranslation()
  const [index, setIndex] = useState(0)
  const [mode, setMode] = useState<FaceBoxMode>("yourAnswer")

  // A round still pending an answer (a game reached mid-play by URL) is dropped, same convention
  // every other *Rounds component already established (§3 H).
  const rounds = game.rounds
    .filter((r): r is WhosThatPersonRoundOut => r.game_type === GameType.WhosThatPerson)
    .filter((r) => r.correct !== null)
  const round = rounds[index]

  if (!round) return null

  const modeOptions: { value: FaceBoxMode; label: string }[] = [
    { value: "yourAnswer", label: t("whosThatPerson.rounds.yourAnswer") },
    { value: "real", label: t("whosThatPerson.rounds.real") },
  ]
  const correctCount = round.faces.filter((face) => face.correct).length

  return (
    <div className="h-dvh w-full overflow-hidden bg-app-bg">
      {/* Unlike live play's IncognitoPhoto, this is always the real, uncensored photo - the player
          already knows every answer by the time they're reviewing. */}
      <AssetPhoto
        key={round.id}
        src={assetThumbnailUrl(round.asset_id)}
        alt=""
        overlay={
          <>
            {round.faces.map((face) => (
              <FaceBoxReadOnly key={face.face_id} face={face} mode={mode} />
            ))}
          </>
        }
      />

      <BackButton label={t("common.back")} onClick={() => onBack?.()} />
      <RoundStepper
        current={index + 1}
        total={rounds.length}
        onPrev={() => setIndex((i) => Math.max(i - 1, 0))}
        onNext={() => setIndex((i) => Math.min(i + 1, rounds.length - 1))}
      />
      {/* Its own row below the stepper rather than crammed onto the same line as it (the doc's
          mockup draws them side by side) - on a narrow phone that'd be four fixed elements
          (back/stepper/toggle/options-menu) fighting over one row's width. */}
      <div className="fixed top-16 left-1/2 z-30 w-44 -translate-x-1/2 md:top-20">
        <SegmentedControl options={modeOptions} value={mode} onChange={setMode} />
      </div>

      <div className="fixed top-[18px] right-[18px] z-30 md:top-7 md:right-10">
        <EntryOptionsMenu>
          <ImmichLink kind="asset" id={round.asset_id} />
        </EntryOptionsMenu>
      </div>

      {round.score_delta !== null && (
        <RevealResultCard
          positionClassName="bottom-[18px] left-[18px] md:bottom-7 md:left-10"
          scoreDelta={round.score_delta}
          subtitle={t("whosThatPerson.result.correctCount", { correct: correctCount, total: round.faces.length })}
        />
      )}
    </div>
  )
}
