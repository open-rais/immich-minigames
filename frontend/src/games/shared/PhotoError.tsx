import { useTranslation } from "react-i18next"

import { Button } from "./Button"

// Same diagonal-stripe fill every failed-image placeholder in the app uses (PersonAvatar.tsx,
// MoreOrLess/PersonPhoto.tsx) - this is the fullscreen/card-sized member of that family, the one
// big enough to also offer a way out.
const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 10px, var(--color-placeholder-b) 10px, var(--color-placeholder-b) 20px)",
}

function BrokenPhotoIcon() {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="text-muted"
    >
      <path d="M3 3l18 18" />
      <path d="M21 15V5a2 2 0 0 0-2-2H9" />
      <path d="M3 7v12a2 2 0 0 0 2 2h12" />
      <path d="M3.5 18.5L9 13l3 3" />
    </svg>
  )
}

// Shown once a photo has spent its whole retry budget (see imageLoading.ts / thumbnailQueue.ts).
// Deliberately only used on surfaces big enough to hold a button: a 40px avatar keeps the plain
// striped placeholder, since its photo never blocks play and a control there would be untappable.
//
// `compact` drops the message and shrinks the button for the Timeline track's small cards, which
// are ~112px wide.
export function PhotoError({ onRetry, compact = false }: { onRetry: () => void; compact?: boolean }) {
  const { t } = useTranslation()

  return (
    <div
      className="absolute inset-0 flex items-center justify-center p-2"
      style={placeholderStyle}
    >
      {/* Own surface behind the content - the stripes underneath make text and a button border
          hard to read on their own, in either theme. */}
      <div className="flex max-w-full flex-col items-center gap-2 rounded-2xl bg-surface/95 px-4 py-3 text-center shadow-card">
        <BrokenPhotoIcon />
        {!compact && <p className="text-sm font-semibold text-body">{t("common.photoFailed")}</p>}
        <Button
          variant="secondary"
          className={compact ? "px-3 py-1 text-xs" : "px-5 py-2"}
          onClick={onRetry}
        >
          {t("common.error.retry")}
        </Button>
      </div>
    </div>
  )
}
