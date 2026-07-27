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

// Single source for column order/labels - drives GuessTable's header row and every body row (both
// the static one and AnimatedGuessRow's), so they can't drift out of sync. computeTarget (roadmap
// #10) is the target row's own value for that same column - kept paired here rather than as a
// second lookup, for the same reason. Split into its own module (not exported from GuessTable.tsx
// itself) purely so oxlint's react-refresh rule doesn't flag a component file for exporting
// non-component values.
export const CLUE_COLUMNS = [
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

// Fixed width on mobile (flex-none), but grows on desktop (flex-1, with md:min-w-56 as a floor) to
// absorb whatever's left over inside the page's own max-w-5xl container - the 6 CLUE_COL tiles are
// always flex-none/fixed, so this is what was leaving a dead strip of empty space to the right of
// the table on wide desktop viewports, and what now instead pushes the clue tiles flush to the
// row's right edge as a side effect of PERSON_COL simply taking the slack.
export const PERSON_COL = "w-28 flex-none md:min-w-56 md:flex-1"
export const CLUE_COL = "w-20 flex-none md:w-28"

// A body row (target/static/animated) is a bit taller than its tiles' own aspect-square height on
// mobile only, to give the stacked avatar-above-name PersonCell layout some breathing room - desktop
// resets to no minimum since its side-by-side PersonCell layout is already comfortably short.
export const ROW_MIN_H_CLASS = "min-h-24 md:min-h-0"
// Flex row's default align-items:stretch means every cell stretches to match ROW_MIN_H_CLASS above,
// taller than a clue tile's own aspect-square box - center it within that extra room instead of
// leaving it pinned to the top.
export const CLUE_CELL_WRAPPER_CLASS = `${CLUE_COL} flex items-center justify-center p-1 md:p-1.5`
