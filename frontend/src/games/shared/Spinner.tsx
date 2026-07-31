// Small centered loading indicator shown while a photo's <img> hasn't fired onLoad yet - shared by
// AssetPhoto.tsx and Timeline/TimelineCard.tsx so both fade-in patterns get the same spinner instead
// of duplicating the same SVG markup.
export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={`animate-spin text-muted ${className}`}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.25" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  )
}
