import { useTranslation } from "react-i18next"

import type { ImmichdleRoundOut } from "../../api/types"
import { ageClue, assetCountClue, assetsTogetherClue, commonNamesClue, firstAppearanceClue, mlSimilarityClue } from "./clueColors"
import { ClueCell } from "./ClueCell"
import { PersonCell } from "./PersonCell"

// Single source for column order/labels - drives both the header row and every body row, so the
// two can't drift out of sync.
const CLUE_COLUMNS = [
  { key: "age", labelKey: "immichdle.clues.age", compute: ageClue },
  { key: "assetCount", labelKey: "immichdle.clues.assetCount", compute: assetCountClue },
  { key: "firstAppearance", labelKey: "immichdle.clues.firstAppearance", compute: firstAppearanceClue },
  { key: "commonNames", labelKey: "immichdle.clues.commonNames", compute: commonNamesClue },
  { key: "mlSimilarity", labelKey: "immichdle.clues.mlSimilarity", compute: mlSimilarityClue },
  { key: "assetsTogether", labelKey: "immichdle.clues.assetsTogether", compute: assetsTogetherClue },
] as const

const PERSON_COL = "w-28 flex-none md:w-36"
const CLUE_COL = "w-20 flex-none md:w-24"

// Every past guess as a table: person column on the left (face over name), then one square tile per
// clue - column labels appear once, in the header row, rather than being repeated on every tile.
// `inline-flex flex-col` makes the table size to its own natural (widest-row) width rather than
// shrinking to the container, so the surrounding `overflow-x-auto` scrolls *inside* the table when
// it doesn't fit, instead of the whole page growing wider.
export function GuessTable({ history }: { history: ImmichdleRoundOut[] }) {
  const { t } = useTranslation()

  if (history.length === 0) return null

  return (
    <div className="w-full overflow-x-auto rounded-2xl border border-line bg-surface shadow-card">
      <div className="inline-flex min-w-full flex-col">
        <div className="flex border-b border-line">
          <div className={PERSON_COL} />
          {CLUE_COLUMNS.map((column) => (
            <div
              key={column.key}
              className={`${CLUE_COL} flex items-center justify-center p-1 text-center text-[10px] font-bold tracking-wide text-muted uppercase md:text-[11px]`}
            >
              {t(column.labelKey)}
            </div>
          ))}
        </div>

        {history.map((round) => (
          <div key={round.id} className={`flex border-t border-line first:border-t-0 ${round.correct ? "bg-clue-match/10" : ""}`}>
            <div className={PERSON_COL}>
              <PersonCell round={round} />
            </div>
            {CLUE_COLUMNS.map((column) => (
              <div key={column.key} className={`${CLUE_COL} p-1`}>
                <ClueCell clue={column.compute(round)} />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
