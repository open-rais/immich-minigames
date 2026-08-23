import type { BirthdayDayMonthAlternative, PersonRef } from "../../api/types/trivium"

// One i18n key per question_kind the backend can send - see games/trivium/questions/ on the
// backend for the bank this mirrors. A kind missing here (a backend ahead of this frontend build)
// falls back to the error screen rather than rendering a raw, untranslated key. Shared between
// TriviumGame.tsx (live play) and TriviumRounds.tsx (review) - both render the exact same
// question_kind -> phrase mapping, just with a different reveal state around it.
export const QUESTION_TEXT_KEYS: Record<string, string> = {
  birthday_year: "trivium.questions.birthdayYear",
  birthday_day_month: "trivium.questions.birthdayDayMonth",
  birthday_full_date: "trivium.questions.birthdayFullDate",
  photos_total_assets: "trivium.questions.photosTotalAssets",
  photos_together: "trivium.questions.photosTogether",
  photos_first_asset_year: "trivium.questions.photosFirstAssetYear",
  location_country: "trivium.questions.locationCountry",
  location_city: "trivium.questions.locationCity",
  mixed_face_to_name: "trivium.questions.mixedFaceToName",
  mixed_name_to_face: "trivium.questions.mixedNameToFace",
}

// question_kinds whose alternatives are people ({person_id, person_name}) rather than a raw
// value - photos_total_assets/photos_together: the choices themselves are the candidates being
// compared, not a number or date about a single named subject. mixed_name_to_face: same shape,
// its alternatives are the 4 candidate faces for "who is {name}".
export const PERSON_ALTERNATIVE_KINDS = new Set(["photos_total_assets", "photos_together", "mixed_name_to_face"])

// Of PERSON_ALTERNATIVE_KINDS, the ones meant to be told apart by face alone - mixed_name_to_face
// ("who is {name}") would give away the answer if each candidate's name were printed under their
// photo. photos_total_assets/photos_together are the opposite: the name is the very thing being
// compared, so they keep their caption (see TriviumOption.tsx's hideCaption).
export const FACE_ONLY_ALTERNATIVE_KINDS = new Set(["mixed_name_to_face"])

// Formats one alternative for display, per question_kind - birthday_year/photos_first_asset_year's
// are plain numbers (rendered as-is), birthday_day_month/birthday_full_date carry no pre-built
// phrase either (same "structured data, not a formatted string" rule as the question text itself),
// so the frontend formats them per the active language via Intl.DateTimeFormat. UTC avoids the
// formatted day shifting by the viewer's own timezone offset - these are calendar dates, not
// instants. photos_total_assets/photos_together/mixed_name_to_face's alternatives are people -
// just their name.
export interface QuestionSegment {
  word: string
  bold: boolean
}

// Parses `**marked**` spans out of an already-interpolated question string (i18next fills in
// {{name}} etc. before this ever sees the text - TriviumGame.tsx/TriviumRounds.tsx both call
// t(questionTextKey, { name }) first) into a flat, ordered list of words each tagged with whether
// it falls inside a bold span - the keyword and/or the person's name, per the 10 trivium.questions.*
// locale strings. Splits on `**` first, alternating the bold flag, and only *then* splits each
// resulting chunk on whitespace - never the other way around, since a mark can span more than one
// word (an interpolated {{name}} like "Ana María" becomes **Ana María**, both words bold). Same
// word count/order as a plain whitespace split on the marker-free text, so the word-by-word reveal
// timing this feeds (TriviumGame.tsx's WORD_REVEAL_MS) doesn't change. A phrase with no `**` at all
// (a locale that hasn't been updated yet) degrades to every word unbold rather than throwing.
export function questionSegments(text: string): QuestionSegment[] {
  const parts = text.split("**")
  const segments: QuestionSegment[] = []
  parts.forEach((part, i) => {
    const bold = i % 2 === 1
    for (const word of part.split(/\s+/)) {
      if (word) segments.push({ word, bold })
    }
  })
  return segments
}

export function formatAlternative(questionKind: string, value: unknown, language: string): string {
  if (PERSON_ALTERNATIVE_KINDS.has(questionKind)) {
    return (value as PersonRef).person_name
  }
  if (questionKind === "birthday_day_month") {
    const { month, day } = value as BirthdayDayMonthAlternative
    const date = new Date(Date.UTC(2000, month - 1, day))
    return new Intl.DateTimeFormat(language, { month: "long", day: "numeric", timeZone: "UTC" }).format(date)
  }
  if (questionKind === "birthday_full_date") {
    const date = new Date(`${value as string}T00:00:00Z`)
    return new Intl.DateTimeFormat(language, {
      year: "numeric",
      month: "long",
      day: "numeric",
      timeZone: "UTC",
    }).format(date)
  }
  return String(value)
}
