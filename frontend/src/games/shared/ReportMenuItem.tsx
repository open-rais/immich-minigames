import { useState } from "react"
import { useTranslation } from "react-i18next"

import { ReportModal } from "./ReportModal"

interface ReportMenuItemProps {
  kind: "asset" | "person" | "album" // same type as ImmichLink.tsx's ImmichLinkProps.kind
  id: string
}

// Same menu-row styling/layout as ImmichLink.tsx, but a <button> (not an <a>, hence w-full
// text-left to match that anchor's block layout) in the danger token (Button.tsx's own
// variant="danger" text color) rather than the neutral text-body every other row uses - it's a
// "something's wrong here" action, not a neutral navigation link. Opens ReportModal, meant to live
// inside EntryOptionsMenu.tsx alongside ImmichLink.
export function ReportMenuItem({ kind, id }: ReportMenuItemProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="block w-full rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-danger hover:bg-hover-tint"
      >
        {t("reports.menuItem")}
      </button>
      {open && <ReportModal kind={kind} id={id} onClose={() => setOpen(false)} />}
    </>
  )
}
