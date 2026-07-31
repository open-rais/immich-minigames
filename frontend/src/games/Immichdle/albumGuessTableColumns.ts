import {
  assetCountClue,
  assetCountTargetClue,
  commonNamesClue,
  commonNamesTargetClue,
  firstAssetDateClue,
  firstAssetDateTargetClue,
  similarityClue,
  similarityTargetClue,
  uniqueFaceCountClue,
  uniqueFaceCountTargetClue,
} from "./albumClueColors"

// The 5 clues that render through the shared ClueCell (mirrors guessTableColumns.ts's
// CLUE_COLUMNS) - the 6th, dominant face, isn't here since it renders through
// AlbumDominantFaceCell instead (see AlbumGuessTable.tsx/AlbumAnimatedGuessRow.tsx, which each
// split this array around it - the first 2 entries render before it, the remaining 3 after) so the
// on-screen order matches ROADMAP.md's own listing exactly: first_asset_date, assets, dominant
// face, common names, similarity, unique faces.
export const ALBUM_CLUE_COLUMNS = [
  {
    key: "firstAssetDate",
    labelKey: "immichdle.album.clues.firstAssetDate",
    compute: firstAssetDateClue,
    computeTarget: firstAssetDateTargetClue,
  },
  {
    key: "assetCount",
    labelKey: "immichdle.album.clues.assetCount",
    compute: assetCountClue,
    computeTarget: assetCountTargetClue,
  },
  {
    key: "commonNames",
    labelKey: "immichdle.album.clues.commonNames",
    compute: commonNamesClue,
    computeTarget: commonNamesTargetClue,
  },
  {
    key: "similarity",
    labelKey: "immichdle.album.clues.similarity",
    compute: similarityClue,
    computeTarget: similarityTargetClue,
  },
  {
    key: "uniqueFaceCount",
    labelKey: "immichdle.album.clues.uniqueFaceCount",
    compute: uniqueFaceCountClue,
    computeTarget: uniqueFaceCountTargetClue,
  },
] as const

// Split once here (not re-sliced independently in every consumer) so the "where does dominant
// face go" boundary can't drift between the static table and the animated reveal sequence.
export const ALBUM_CLUE_COLUMNS_BEFORE_DOMINANT_FACE = ALBUM_CLUE_COLUMNS.slice(0, 2)
export const ALBUM_CLUE_COLUMNS_AFTER_DOMINANT_FACE = ALBUM_CLUE_COLUMNS.slice(2)
