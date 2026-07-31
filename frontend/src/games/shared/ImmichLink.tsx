import { useTranslation } from "react-i18next"

import { useImmichLinks } from "../../api/config"

interface ImmichLinkProps {
  kind: "asset" | "person" | "album"
  id: string
  className?: string
}

/** "Ver en Immich" deep link - renders nothing if Immich's
 * public URL isn't configured, so callers never need their own conditional around this. Styled as
 * a menu row (see EntryOptionsMenu.tsx), matching menu/UserMenu.tsx's own account/language/theme
 * rows - it's meant to live inside that "..." popover, not stand alone. */
export function ImmichLink({ kind, id, className = "" }: ImmichLinkProps) {
  const { t } = useTranslation()
  const links = useImmichLinks()
  if (!links) return null

  const href =
    kind === "asset"
      ? links.assetUrl(id)
      : kind === "person"
        ? links.personUrl(id)
        : links.albumUrl(id)

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`block rounded-xl px-3 py-2.5 text-sm font-semibold text-body hover:bg-hover-tint ${className}`}
    >
      {t("common.viewInImmich")}
    </a>
  )
}
