import { useTranslation } from "react-i18next"

import type { AlbumdleRoundOut } from "../../api/types/immichdle"
import { EntryOptionsMenu } from "../shared/EntryOptionsMenu"
import { ImmichLink } from "../shared/ImmichLink"
import type { AlbumTargetSnapshot } from "./albumClueColors"
import {
  ALBUM_CLUE_COLUMNS_AFTER_DOMINANT_FACE,
  ALBUM_CLUE_COLUMNS_BEFORE_DOMINANT_FACE,
} from "./albumGuessTableColumns"
import { AlbumAnimatedGuessRow } from "./AlbumAnimatedGuessRow"
import { AlbumCell } from "./AlbumCell"
import { AlbumDominantFaceCell } from "./AlbumDominantFaceCell"
import { ClueCell } from "./ClueCell"
import { CLUE_CELL_WRAPPER_CLASS, CLUE_COL, PERSON_COL, ROW_MIN_H_CLASS } from "./guessTableColumns"

const ACTIONS_COL = "w-10 flex-none md:w-12"

const HEADER_CELL_CLASS = `${CLUE_COL} flex items-center justify-center p-1 text-center text-[10px] font-bold tracking-wide text-muted uppercase md:p-2 md:text-xs`

interface AlbumGuessTableProps {
  history: AlbumdleRoundOut[]
  // When present, draws the target's own row above the guesses and adds a "Ver en Immich" menu to
  // every row - same contract as GuessTable's own `target` prop.
  target?: AlbumTargetSnapshot
  animatingRoundId?: string | null
  onRowAnimationDone?: () => void
}

// Every past guess as a table - mirrors games/Immichdle/GuessTable.tsx exactly, substituting
// albums for people. Column order matches ROADMAP.md's own clue listing exactly: first_asset_date,
// assets, dominant face, common names, similarity, unique faces - so AlbumDominantFaceCell is
// slotted in between ALBUM_CLUE_COLUMNS_BEFORE_DOMINANT_FACE (2 columns) and
// ALBUM_CLUE_COLUMNS_AFTER_DOMINANT_FACE (3 columns) rather than at either end.
export function AlbumGuessTable({
  history,
  target,
  animatingRoundId,
  onRowAnimationDone,
}: AlbumGuessTableProps) {
  const { t } = useTranslation()

  if (history.length === 0 && !target) return null

  return (
    <div className="w-full overflow-x-auto rounded-2xl border border-line bg-surface shadow-card">
      <div className="inline-flex min-w-full flex-col">
        <div className="flex border-b border-line">
          <div className={PERSON_COL} />
          {ALBUM_CLUE_COLUMNS_BEFORE_DOMINANT_FACE.map((column) => (
            <div key={column.key} className={HEADER_CELL_CLASS}>
              {t(column.labelKey)}
            </div>
          ))}
          <div className={HEADER_CELL_CLASS}>{t("immichdle.album.clues.dominantFace")}</div>
          {ALBUM_CLUE_COLUMNS_AFTER_DOMINANT_FACE.map((column) => (
            <div key={column.key} className={HEADER_CELL_CLASS}>
              {t(column.labelKey)}
            </div>
          ))}
          {target && <div className={ACTIONS_COL} />}
        </div>

        {target && (
          <div className={`flex border-t border-line ${ROW_MIN_H_CLASS}`}>
            <div className={PERSON_COL}>
              <AlbumCell albumId={target.albumId} name={target.name} />
            </div>
            {ALBUM_CLUE_COLUMNS_BEFORE_DOMINANT_FACE.map((column) => (
              <div key={column.key} className={CLUE_CELL_WRAPPER_CLASS}>
                <ClueCell clue={column.computeTarget(target)} />
              </div>
            ))}
            <div className={CLUE_CELL_WRAPPER_CLASS}>
              <AlbumDominantFaceCell
                personId={target.dominantPersonId}
                name={target.dominantPersonName}
                extraCount={target.dominantExtraCount}
                comparison={target.dominantPersonId ? "match" : null}
              />
            </div>
            {ALBUM_CLUE_COLUMNS_AFTER_DOMINANT_FACE.map((column) => (
              <div key={column.key} className={CLUE_CELL_WRAPPER_CLASS}>
                <ClueCell clue={column.computeTarget(target)} />
              </div>
            ))}
            <div className={`${ACTIONS_COL} flex items-center justify-center`}>
              <EntryOptionsMenu>
                <ImmichLink kind="album" id={target.albumId} />
              </EntryOptionsMenu>
            </div>
          </div>
        )}

        {history.map((round) =>
          round.id === animatingRoundId ? (
            <AlbumAnimatedGuessRow key={round.id} round={round} onDone={() => onRowAnimationDone?.()} />
          ) : (
            <div
              key={round.id}
              className={`flex border-t border-line first:border-t-0 ${ROW_MIN_H_CLASS}`}
            >
              <div className={PERSON_COL}>
                <AlbumCell albumId={round.guess_album_id!} name={round.guess_album_name} />
              </div>
              {ALBUM_CLUE_COLUMNS_BEFORE_DOMINANT_FACE.map((column) => (
                <div key={column.key} className={CLUE_CELL_WRAPPER_CLASS}>
                  <ClueCell clue={column.compute(round)} />
                </div>
              ))}
              <div className={CLUE_CELL_WRAPPER_CLASS}>
                <AlbumDominantFaceCell
                  personId={round.clues!.dominant_face_person_id}
                  name={round.clues!.dominant_face_name}
                  extraCount={round.clues!.dominant_face_extra_count}
                  comparison={round.clues!.dominant_face_comparison}
                />
              </div>
              {ALBUM_CLUE_COLUMNS_AFTER_DOMINANT_FACE.map((column) => (
                <div key={column.key} className={CLUE_CELL_WRAPPER_CLASS}>
                  <ClueCell clue={column.compute(round)} />
                </div>
              ))}
              {target && (
                <div className={`${ACTIONS_COL} flex items-center justify-center`}>
                  <EntryOptionsMenu>
                    <ImmichLink kind="album" id={round.guess_album_id!} />
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
