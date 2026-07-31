import { useTranslation } from "react-i18next"

import type { ImmichdleRoundOut } from "../../api/types/immichdle"
import { EntryOptionsMenu } from "../shared/EntryOptionsMenu"
import { ImmichLink } from "../shared/ImmichLink"
import type { TargetSnapshot } from "./clueColors"
import { AnimatedGuessRow } from "./AnimatedGuessRow"
import { ClueCell } from "./ClueCell"
import {
  CLUE_CELL_WRAPPER_CLASS,
  CLUE_COL,
  CLUE_COLUMNS,
  PERSON_COL,
  ROW_MIN_H_CLASS,
} from "./guessTableColumns"
import { PersonCell } from "./PersonCell"

const ACTIONS_COL = "w-10 flex-none md:w-12"

interface GuessTableProps {
  history: ImmichdleRoundOut[]
  // When present, draws the target's own row above the guesses and adds a "Ver en Immich" menu to
  // every row. Undefined during live
  // play (ImmichdleGame.tsx never has the target - it's redacted until the game finishes), which
  // keeps this table looking exactly as it always has there.
  target?: TargetSnapshot
  // The guess-reveal sequence - when this matches a row in
  // `history`, that row renders as an AnimatedGuessRow instead of the plain static row below.
  // Undefined in the rounds-review table (ImmichdleRounds.tsx never passes it), which keeps that
  // table exactly as it's always looked - a finished game has nothing left to animate.
  animatingRoundId?: string | null
  onRowAnimationDone?: () => void
}

// Every past guess as a table: person column on the left (face over name), then one square tile per
// clue - column labels appear once, in the header row, rather than being repeated on every tile.
// `inline-flex flex-col` makes the table size to its own natural (widest-row) width rather than
// shrinking to the container, so the surrounding `overflow-x-auto` scrolls *inside* the table when
// it doesn't fit, instead of the whole page growing wider.
export function GuessTable({
  history,
  target,
  animatingRoundId,
  onRowAnimationDone,
}: GuessTableProps) {
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
          <div className={`flex border-t border-line ${ROW_MIN_H_CLASS}`}>
            <div className={PERSON_COL}>
              <PersonCell personId={target.personId} name={target.name} />
            </div>
            {CLUE_COLUMNS.map((column) => (
              <div key={column.key} className={CLUE_CELL_WRAPPER_CLASS}>
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

        {history.map((round) =>
          round.id === animatingRoundId ? (
            <AnimatedGuessRow key={round.id} round={round} onDone={() => onRowAnimationDone?.()} />
          ) : (
            <div
              key={round.id}
              className={`flex border-t border-line first:border-t-0 ${ROW_MIN_H_CLASS}`}
            >
              <div className={PERSON_COL}>
                <PersonCell personId={round.guess_person_id!} name={round.guess_person_name} />
              </div>
              {CLUE_COLUMNS.map((column) => (
                <div key={column.key} className={CLUE_CELL_WRAPPER_CLASS}>
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
          ),
        )}
      </div>
    </div>
  )
}
