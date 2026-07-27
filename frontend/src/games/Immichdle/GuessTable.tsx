import { useTranslation } from "react-i18next"

import type { ImmichdleRoundOut } from "../../api/types"
import { EntryOptionsMenu } from "../shared/EntryOptionsMenu"
import { ImmichLink } from "../shared/ImmichLink"
import {
  ageClue,
  ageTargetClue,
  assetCountClue,
  assetCountTargetClue,
  assetsTogetherClue,
  assetsTogetherTargetClue,
  commonNamesClue,
  commonNamesTargetClue,
  firstAppearanceClue,
  firstAppearanceTargetClue,
  mlSimilarityClue,
  mlSimilarityTargetClue,
} from "./clueColors"
import type { TargetSnapshot } from "./clueColors"
import { ClueCell } from "./ClueCell"
import { PersonCell } from "./PersonCell"

// Single source for column order/labels - drives both the header row and every body row, so the
// two can't drift out of sync. computeTarget (roadmap #10) is the target row's own value for that
// same column - kept paired here rather than as a second lookup, for the same reason.
const CLUE_COLUMNS = [
  { key: "age", labelKey: "immichdle.clues.age", compute: ageClue, computeTarget: ageTargetClue },
  { key: "assetCount", labelKey: "immichdle.clues.assetCount", compute: assetCountClue, computeTarget: assetCountTargetClue },
  {
    key: "firstAppearance",
    labelKey: "immichdle.clues.firstAppearance",
    compute: firstAppearanceClue,
    computeTarget: firstAppearanceTargetClue,
  },
  { key: "commonNames", labelKey: "immichdle.clues.commonNames", compute: commonNamesClue, computeTarget: commonNamesTargetClue },
  { key: "mlSimilarity", labelKey: "immichdle.clues.mlSimilarity", compute: mlSimilarityClue, computeTarget: mlSimilarityTargetClue },
  {
    key: "assetsTogether",
    labelKey: "immichdle.clues.assetsTogether",
    compute: assetsTogetherClue,
    computeTarget: assetsTogetherTargetClue,
  },
] as const

const PERSON_COL = "w-28 flex-none md:w-56"
const CLUE_COL = "w-20 flex-none md:w-28"
const ACTIONS_COL = "w-10 flex-none md:w-12"

interface GuessTableProps {
  history: ImmichdleRoundOut[]
  // Roadmap #10 (rounds review) - when present, draws the target's own row above the guesses
  // (ROUNDS-VIEW.md §3 F/§4.6) and adds a "Ver en Immich" menu to every row. Undefined during live
  // play (ImmichdleGame.tsx never has the target - it's redacted until the game finishes), which
  // keeps this table looking exactly as it always has there.
  target?: TargetSnapshot
}

// Every past guess as a table: person column on the left (face over name), then one square tile per
// clue - column labels appear once, in the header row, rather than being repeated on every tile.
// `inline-flex flex-col` makes the table size to its own natural (widest-row) width rather than
// shrinking to the container, so the surrounding `overflow-x-auto` scrolls *inside* the table when
// it doesn't fit, instead of the whole page growing wider.
export function GuessTable({ history, target }: GuessTableProps) {
  const { t } = useTranslation()

  if (history.length === 0 && !target) return null

  return (
    <div className="w-full overflow-x-auto rounded-2xl border border-line bg-surface shadow-card">
      <div className="inline-flex min-w-full flex-col">
        <div className="flex border-b border-line">
          <div className={PERSON_COL} />
          {CLUE_COLUMNS.map((column) => (
            <div
              key={column.key}
              className={`${CLUE_COL} flex items-center justify-center p-1 text-center text-[10px] font-bold tracking-wide text-muted uppercase md:p-2 md:text-xs`}
            >
              {t(column.labelKey)}
            </div>
          ))}
          {target && <div className={ACTIONS_COL} />}
        </div>

        {target && (
          <div className="flex border-t border-line">
            <div className={PERSON_COL}>
              <PersonCell personId={target.personId} name={target.name} />
            </div>
            {CLUE_COLUMNS.map((column) => (
              <div key={column.key} className={`${CLUE_COL} p-1 md:p-1.5`}>
                <ClueCell clue={column.computeTarget(target)} />
              </div>
            ))}
            <div className={`${ACTIONS_COL} flex items-center justify-center`}>
              <EntryOptionsMenu>
                <ImmichLink kind="person" id={target.personId} />
              </EntryOptionsMenu>
            </div>
          </div>
        )}

        {history.map((round) => (
          <div key={round.id} className={`flex border-t border-line first:border-t-0 ${round.correct ? "bg-clue-match/10" : ""}`}>
            <div className={PERSON_COL}>
              <PersonCell personId={round.guess_person_id!} name={round.guess_person_name} />
            </div>
            {CLUE_COLUMNS.map((column) => (
              <div key={column.key} className={`${CLUE_COL} p-1 md:p-1.5`}>
                <ClueCell clue={column.compute(round)} />
              </div>
            ))}
            {target && (
              <div className={`${ACTIONS_COL} flex items-center justify-center`}>
                <EntryOptionsMenu>
                  <ImmichLink kind="person" id={round.guess_person_id!} />
                </EntryOptionsMenu>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
