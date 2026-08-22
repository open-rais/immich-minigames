import { useTranslation } from "react-i18next"

import { assetThumbnailUrl, personThumbnailUrl } from "../../api/games"
import { GameType } from "../../api/types/common"
import type { RoundOut } from "../../api/types/common"
import type { PersonRef, TriviumRoundOut } from "../../api/types/trivium"
import type { RoundsComponentProps } from "../catalog"
import { AssetPhoto } from "../shared/AssetPhoto"
import { BackButton } from "../shared/BackButton"
import { EntryOptionsMenu } from "../shared/EntryOptionsMenu"
import { ImmichLink } from "../shared/ImmichLink"
import { PersonAvatar } from "../shared/PersonAvatar"
import { ReportMenuItem } from "../shared/ReportMenuItem"
import { RevealResultCard } from "../shared/RevealResultCard"
import { RoundStepper } from "../rounds/RoundStepper"
import { useRoundStepper } from "../shared/useRoundStepper"
import { FACE_ONLY_ALTERNATIVE_KINDS, PERSON_ALTERNATIVE_KINDS, QUESTION_TEXT_KEYS, formatAlternative } from "./questionText"
import type { TriviumOptionState } from "./TriviumOption"
import { TriviumOption } from "./TriviumOption"

function isTriviumRound(round: RoundOut): round is TriviumRoundOut {
  return round.game_type === GameType.Trivium
}

// Which entity (if any) "Ver en Immich"/"Reportar" apply to, per question_kind - the round's own
// media is the obvious choice when there is one (an asset for location_*, the subject's face for
// birthday_*/photos_together/mixed_face_to_name). photos_total_assets/mixed_name_to_face have no
// media of their own (params has no {persona} either for the former) - the correct alternative is
// the next best single, unambiguous entity to report a name/face mismatch against.
function entityFor(round: TriviumRoundOut): { kind: "asset" | "person"; id: string } | null {
  if (round.media.kind === "asset" && round.media.asset_id) {
    return { kind: "asset", id: round.media.asset_id }
  }
  if (round.media.kind === "person_thumbnail" && round.media.person_id) {
    return { kind: "person", id: round.media.person_id }
  }
  const paramsPersonId = (round.params as { person_id?: string }).person_id
  if (paramsPersonId) {
    return { kind: "person", id: paramsPersonId }
  }
  if (PERSON_ALTERNATIVE_KINDS.has(round.question_kind) && round.correct_index !== null) {
    const correct = round.alternatives[round.correct_index] as PersonRef
    return { kind: "person", id: correct.person_id }
  }
  return null
}

// Steps through an already-finished Trivium game's rounds, one at a time, exactly as they looked
// right after their reveal - mirrors TriviumGame.tsx's own revealed-round layout (same card,
// same TriviumOption states), minus the reveal animation/timer, which have nothing left to do once
// every round is already answered. "fullscreen" family (own stepper state, own BackButton), same
// shape as Geoguessr/Dateguessr/Who'sThatPerson's rounds review.
export function TriviumRounds({ game, onBack }: RoundsComponentProps) {
  const { t, i18n } = useTranslation()

  // A round still pending an answer (a game reached mid-play by URL) is dropped, same convention
  // every other *Rounds component already established.
  const stepper = useRoundStepper(game, isTriviumRound, (r) => r.correct !== null)

  if (!stepper) return null
  const { round, index, total, prev, next } = stepper

  const questionTextKey = QUESTION_TEXT_KEYS[round.question_kind]
  const params = round.params as unknown as PersonRef
  const questionText = questionTextKey ? t(questionTextKey, { name: params.person_name }) : ""

  const personThumbnailSrc =
    round.media.kind === "person_thumbnail" && round.media.person_id
      ? personThumbnailUrl(round.media.person_id)
      : null
  const assetPhotoSrc =
    round.media.kind === "asset" && round.media.asset_id ? assetThumbnailUrl(round.media.asset_id) : null

  const hasPersonAlternatives = PERSON_ALTERNATIVE_KINDS.has(round.question_kind)
  const alternativeLabels = round.alternatives.map((alt) => formatAlternative(round.question_kind, alt, i18n.language))
  const optionPhotoUrls: (string | undefined)[] = hasPersonAlternatives
    ? round.alternatives.map((alt) => personThumbnailUrl((alt as PersonRef).person_id))
    : [undefined, undefined, undefined, undefined]

  const optionState = (i: number): TriviumOptionState => {
    if (i === round.correct_index) return "correct"
    if (round.guess !== null && i === round.guess) return "wrong"
    return "muted"
  }

  const resultKey = round.correct
    ? "trivium.result.correct"
    : round.guess === null
      ? "trivium.result.timeout"
      : "trivium.result.wrong"
  // No detail line on a timeout - elapsed_ms is just the answer window's own length, not a
  // meaningful "how fast" figure.
  const detail =
    round.guess !== null && round.elapsed_ms !== null
      ? t("trivium.rounds.answeredIn", { seconds: (round.elapsed_ms / 1000).toFixed(1) })
      : undefined

  const entity = entityFor(round)

  return (
    <div className="flex h-dvh flex-col justify-between overflow-hidden bg-app-bg px-6 pt-20 pb-8 md:px-10 md:pt-28 md:pb-12">
      <BackButton label={t("common.back")} onClick={() => onBack?.()} />
      <RoundStepper current={index + 1} total={total} onPrev={prev} onNext={next} />

      {entity && (
        // z-40 (not the usual z-30 wrapper - see Geoguessr/WhosThatPersonRounds) - this wrapper's
        // own `fixed` positioning makes it a stacking context, which would otherwise trap
        // EntryOptionsMenu's popover (internally z-40) below RevealResultCard's z-30 once open:
        // elsewhere the two never overlap (opposite corners), but here they're both top-right and
        // close together, so the trap was actually visible.
        <div className="fixed top-[18px] right-[18px] z-40 md:top-7 md:right-10">
          <EntryOptionsMenu>
            <ImmichLink kind={entity.kind} id={entity.id} />
            <ReportMenuItem kind={entity.kind} id={entity.id} />
          </EntryOptionsMenu>
        </div>
      )}

      <div className="mx-auto flex w-full max-w-md flex-col items-center md:max-w-2xl">
        <div className="flex w-full flex-col items-center gap-4 rounded-[22px] border border-line bg-surface p-6 text-center shadow-card md:rounded-3xl md:p-10">
          {round.media.kind === "person_thumbnail" && <PersonAvatar src={personThumbnailSrc} alt="" size="lg" />}
          {round.media.kind === "asset" && assetPhotoSrc && (
            <div className="relative h-48 w-full overflow-hidden rounded-2xl md:h-64">
              <AssetPhoto src={assetPhotoSrc} alt="" />
            </div>
          )}
          <p className="text-xl font-bold text-ink md:text-2xl">{questionText}</p>
        </div>
      </div>

      {round.score_delta !== null && (
        <RevealResultCard
          positionClassName="top-[70px] right-[18px] md:top-24 md:right-10"
          scoreDelta={round.score_delta}
          subtitle={t(resultKey)}
          detail={detail}
        />
      )}

      <div className="mx-auto flex w-full max-w-md flex-col items-center gap-4 md:max-w-2xl">
        <div
          className={`grid w-full gap-3 md:gap-5 ${hasPersonAlternatives ? "grid-cols-2" : "grid-cols-1 md:grid-cols-2"}`}
        >
          {alternativeLabels.map((label, i) => (
            <TriviumOption
              key={i}
              state={optionState(i)}
              disabled
              photoUrl={optionPhotoUrls[i]}
              hideCaption={FACE_ONLY_ALTERNATIVE_KINDS.has(round.question_kind)}
            >
              {label}
            </TriviumOption>
          ))}
        </div>
      </div>
    </div>
  )
}
