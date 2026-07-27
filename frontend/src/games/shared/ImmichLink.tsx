import { useTranslation } from "react-i18next"

import { useImmichLinks } from "../../api/config"

interface ImmichLinkProps {
  kind: "asset" | "person" | "album"
  id: string
  className?: string
}

/** "Ver en Immich" deep link (ROUNDS-VIEW.md roadmap point #10) - renders nothing if Immich's
 * public URL isn't configured, so callers never need their own conditional around this. */
export function ImmichLink({ kind, id, className = "" }: ImmichLinkProps) {
  const { t } = useTranslation()
  const links = useImmichLinks()
  if (!links) return null

  const href = kind === "asset" ? links.assetUrl(id) : kind === "person" ? links.personUrl(id) : links.albumUrl(id)

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`text-sm font-semibold text-primary hover:underline ${className}`}
    >
      {t("common.viewInImmich")} ↗
    </a>
  )
}
