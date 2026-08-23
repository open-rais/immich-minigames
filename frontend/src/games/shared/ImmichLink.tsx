import type { MouseEvent } from "react"
import { useTranslation } from "react-i18next"

import type { ImmichEntityKind } from "../../api/config"
import { useImmichLinks } from "../../api/config"
import { detectMobilePlatform, openInImmichApp } from "./immichDeepLink"

interface ImmichLinkProps {
  kind: ImmichEntityKind
  id: string
  className?: string
}

/** "Ver en Immich" deep link - renders nothing if Immich's
 * public URL isn't configured, so callers never need their own conditional around this. Styled as
 * a menu row (see EntryOptionsMenu.tsx), matching menu/UserMenu.tsx's own account/language/theme
 * rows - it's meant to live inside that "..." popover, not stand alone.
 *
 * The href is always the web URL, so desktop, "open in new tab" and "copy link" all behave like a
 * plain link; a plain tap on a phone is intercepted to try the Immich app first (immichDeepLink.ts). */
export function ImmichLink({ kind, id, className = "" }: ImmichLinkProps) {
  const { t } = useTranslation()
  const links = useImmichLinks()
  if (!links) return null

  const href = links.webUrl(kind, id)

  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    // Let the browser handle anything that isn't a plain left click - those already mean "open this
    // href somewhere", and the app can't honour that.
    if (event.defaultPrevented || event.button !== 0) return
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return

    const platform = detectMobilePlatform()
    if (!platform) return

    event.preventDefault()
    openInImmichApp(platform, links.appUrl(kind, id), href)
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={handleClick}
      className={`block rounded-xl px-3 py-2.5 text-sm font-semibold text-body hover:bg-hover-tint ${className}`}
    >
      {t("common.viewInImmich")}
    </a>
  )
}
