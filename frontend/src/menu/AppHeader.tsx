import { useTranslation } from "react-i18next"

import { UserMenu } from "./UserMenu"

// Same bar shape as Immich's own top header (height/padding/border) - no search bar/upload/
// notifications since those features don't exist here yet. The right side is a single UserMenu
// trigger (roadmap points B/C/D) holding profile/login, language, and theme in one popover, so
// this bar itself stays minimal.
//
// The surface background extends up through `env(safe-area-inset-top)` (needs `viewport-fit=cover`
// in index.html's viewport meta) so it fills the notch/Dynamic Island area on iPhone instead of
// leaving a gap of app-bg color above the bar - the visible h-16 row stays centered below that.
// Sticky (like Immich's own fixed header) so scrolling doesn't slide content into the notch; the
// overscroll rubber-band area above it is handled by index.css's html background gradient instead,
// since sticky elements travel with the page during the bounce.
export function AppHeader() {
  const { t } = useTranslation()

  return (
    <header className="sticky top-0 z-10 border-b border-line bg-surface pt-[env(safe-area-inset-top)]">
      <div className="flex h-16 items-center justify-between px-6 md:px-10">
        <span className="text-xl font-bold text-ink">{t("appHeader.title")}</span>
        <UserMenu />
      </div>
    </header>
  )
}
