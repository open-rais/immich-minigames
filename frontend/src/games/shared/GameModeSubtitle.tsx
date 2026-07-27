interface GameModeSubtitleProps {
  gameTitle: string
  modeTitle: string
}

// Shared by RoundsShell and LeaderboardPage, which both render a "<game> · <mode>" h2. The
// separator is a small CSS-drawn circle, not a text glyph (a U+00B7 middle dot still read as
// lopsided even wrapped in its own span with symmetric margins - its side bearings are baked into
// Overpass's glyph metrics, not fixable via spacing around it).
export function GameModeSubtitle({ gameTitle, modeTitle }: GameModeSubtitleProps) {
  return (
    <h2 className="mt-1 flex items-center justify-center gap-2 text-lg font-semibold text-muted">
      <span>{gameTitle}</span>
      <span className="h-1 w-1 flex-none rounded-full bg-muted" aria-hidden="true" />
      <span>{modeTitle}</span>
    </h2>
  )
}
