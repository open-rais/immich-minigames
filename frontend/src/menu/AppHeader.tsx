import { useTranslation } from "react-i18next"

// Same bar shape as Immich's own top header (height/padding/border) - no icon yet (one is planned
// for later), no search bar/upload/notifications/avatar since none of those features exist here yet.
//
// The white background extends up through `env(safe-area-inset-top)` (needs `viewport-fit=cover`
// in index.html's viewport meta) so it fills the notch/Dynamic Island area on iPhone instead of
// leaving a gap of app-bg color above the bar - the visible h-16 row stays centered below that.
export function AppHeader() {
  const { t } = useTranslation()

  return (
    <header className="border-b border-line bg-white pt-[env(safe-area-inset-top)]">
      <div className="flex h-16 items-center px-6 md:px-10">
        <span className="text-xl font-bold text-ink">{t("appHeader.title")}</span>
      </div>
    </header>
  )
}
