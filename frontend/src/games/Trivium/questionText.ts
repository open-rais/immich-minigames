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
