import type { AlbumdleRoundOut } from "../../api/types/immichdle"
import type { ClueResult } from "./clueColors"

// Mirrors clueColors.ts's pure-function shape exactly, for Albumdle's 5 generic-shaped clues
// (first_asset_date/asset_count/common_names/similarity/unique_face_count). The 6th clue
// (dominant face) isn't here - it needs a thumbnail, not a ClueCell tile, so it's rendered by
// AlbumDominantFaceCell.tsx directly off the raw AlbumdleCluesOut fields instead of a ClueResult.

function dateClue(
  comparison: "before" | "after" | "same" | "unknown",
  close: boolean | null,
  bothUnknown: boolean,
  guessDate: string | null,
): ClueResult {
  if (comparison === "unknown") {
    if (bothUnknown) {
      return { variant: "match", background: null, kind: "text", value: "?" }
    }
    if (guessDate === null) {
      return { variant: "close", background: "question", kind: "text", value: "?" }
    }
    return { variant: "close", background: "question", kind: "date", value: guessDate }
  }
  if (comparison === "same") {
    return { variant: "match", background: null, kind: "date", value: guessDate ?? undefined }
  }
  const direction = comparison === "before" ? "up" : "down"
  return {
    variant: close ? "close" : "miss",
    background: direction,
    kind: "date",
    value: guessDate ?? undefined,
  }
}

export function firstAssetDateClue(round: AlbumdleRoundOut): ClueResult {
  const clues = round.clues!
  return dateClue(
    clues.first_asset_date,
    clues.first_asset_date_close,
    clues.first_asset_date_both_unknown,
    round.guess_first_asset_date,
  )
}

export function assetCountClue(round: AlbumdleRoundOut): ClueResult {
  const clues = round.clues!
  if (clues.asset_count === "equal") {
    return { variant: "match", background: null, kind: "count", value: round.guess_asset_count ?? undefined }
  }
  const direction = clues.asset_count === "less" ? "up" : "down"
  const variant: ClueResult["variant"] = clues.asset_count_close ? "close" : "miss"
  return { variant, background: direction, kind: "count", value: round.guess_asset_count ?? undefined }
}

export function uniqueFaceCountClue(round: AlbumdleRoundOut): ClueResult {
  const clues = round.clues!
  if (clues.unique_face_count === "equal") {
    return {
      variant: "match",
      background: null,
      kind: "count",
      value: round.guess_unique_face_count ?? undefined,
    }
  }
  const direction = clues.unique_face_count === "less" ? "up" : "down"
  const variant: ClueResult["variant"] = clues.unique_face_count_close ? "close" : "miss"
  return { variant, background: direction, kind: "count", value: round.guess_unique_face_count ?? undefined }
}

export function commonNamesClue(round: AlbumdleRoundOut): ClueResult {
  const clues = round.clues!
  const guessWordCount = (round.guess_album_name ?? "").trim().split(/\s+/).filter(Boolean).length
  const variant: ClueResult["variant"] =
    clues.common_names === 0 ? "miss" : clues.common_names === guessWordCount ? "match" : "close"
  return { variant, background: null, kind: "count", value: clues.common_names }
}

// Album-vector (CLIP) cosine similarity reads structurally higher than face similarity even for
// unrelated albums (photos from any two real albums already share a lot of visual structure,
// unlike two unrelated faces) - confirmed with the project owner after playing against the real
// dev library.
const SIMILARITY_CLOSE_THRESHOLD = 0.75

export function similarityClue(round: AlbumdleRoundOut): ClueResult {
  const similarity = round.clues!.similarity
  if (similarity === null) return { variant: "miss", background: null, kind: "text", value: "?" }
  const clamped = Math.max(0, similarity)
  const variant: ClueResult["variant"] =
    similarity === 1 ? "match" : clamped > SIMILARITY_CLOSE_THRESHOLD ? "close" : "miss"
  return { variant, background: null, kind: "percent", value: Math.round(clamped * 100) }
}

// The target row (rounds review) - one xTargetClue per xClue above, all `variant: "match"` and no
// background glyph, mirroring clueColors.ts's own Target* functions.
export interface AlbumTargetSnapshot {
  albumId: string
  name: string
  assetCount: number
  firstAssetDate: string | null
  dominantPersonId: string | null
  dominantPersonName: string | null
  dominantExtraCount: number
  uniqueNamedPersonCount: number
}

export function firstAssetDateTargetClue(target: AlbumTargetSnapshot): ClueResult {
  if (target.firstAssetDate === null) return { variant: "match", background: null, kind: "text", value: "?" }
  return { variant: "match", background: null, kind: "date", value: target.firstAssetDate }
}

export function assetCountTargetClue(target: AlbumTargetSnapshot): ClueResult {
  return { variant: "match", background: null, kind: "count", value: target.assetCount }
}

export function uniqueFaceCountTargetClue(target: AlbumTargetSnapshot): ClueResult {
  return { variant: "match", background: null, kind: "count", value: target.uniqueNamedPersonCount }
}

export function commonNamesTargetClue(target: AlbumTargetSnapshot): ClueResult {
  const wordCount = target.name.trim().split(/\s+/).filter(Boolean).length
  return { variant: "match", background: null, kind: "count", value: wordCount }
}

export function similarityTargetClue(): ClueResult {
  return { variant: "match", background: null, kind: "text", value: "=" }
}
