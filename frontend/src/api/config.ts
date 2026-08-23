import { useEffect, useState } from "react"

import { apiClient } from "./client"
import type { ConfigOut } from "./types/config"

export async function getConfig(): Promise<ConfigOut> {
  const { data } = await apiClient.get<ConfigOut>("/config")
  return data
}

export type ImmichEntityKind = "asset" | "person" | "album"

const WEB_PATHS: Record<ImmichEntityKind, string> = {
  asset: "photos",
  person: "people",
  album: "albums",
}

// The mobile app's deep-link handler reads the intent from the URI's *host* and the id from a query
// param, so these aren't the web paths with a different scheme - "asset" and "album" are singular
// there, and only "people" happens to match.
const APP_HOSTS: Record<ImmichEntityKind, string> = {
  asset: "asset",
  person: "people",
  album: "album",
}

export interface ImmichLinks {
  /** Immich's web UI - desktop, or mobile without the app installed. */
  webUrl: (kind: ImmichEntityKind, id: string) => string
  /** `immich://` deep link into the mobile app, which opens whichever server that app is logged
   * into - so, unlike webUrl, it carries no base URL of its own. */
  appUrl: (kind: ImmichEntityKind, id: string) => string
}

function linksFromBaseUrl(baseUrl: string): ImmichLinks {
  return {
    webUrl: (kind, id) => `${baseUrl}/${WEB_PATHS[kind]}/${id}`,
    appUrl: (kind, id) => `immich://${APP_HOSTS[kind]}?id=${encodeURIComponent(id)}`,
  }
}

// Module-scope cache (not a React Context - only the rounds review view needs this, so a global
// provider would be overkill) shared by every ImmichLink instance on a page, so mounting several at
// once (e.g. one per row of the Immichdle table) still fires exactly one /config request.
let cached: ImmichLinks | null | undefined
let inFlight: Promise<ImmichLinks | null> | null = null

function fetchLinks(): Promise<ImmichLinks | null> {
  if (!inFlight) {
    inFlight = getConfig()
      .then((config) => {
        cached = config.immich_external_url ? linksFromBaseUrl(config.immich_external_url) : null
        return cached
      })
      .catch(() => {
        // Only reset inFlight here, not cached: cached staying undefined (instead of being set to
        // null, "confirmed unconfigured") is what lets the next mount retry instead of a transient
        // /config failure disabling every Immich link for the rest of the tab's session.
        inFlight = null
        return null
      })
  }
  return inFlight
}

// null both while loading and when Immich isn't configured - both cases mean "render nothing",
// which is exactly what ImmichLink.tsx does with this, so no caller needs its own conditional.
export function useImmichLinks(): ImmichLinks | null {
  const [links, setLinks] = useState<ImmichLinks | null>(cached ?? null)

  useEffect(() => {
    if (cached !== undefined) return
    fetchLinks().then(setLinks)
  }, [])

  return links
}
