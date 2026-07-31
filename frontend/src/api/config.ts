import { useEffect, useState } from "react"

import { apiClient } from "./client"
import type { ConfigOut } from "./types/config"

export async function getConfig(): Promise<ConfigOut> {
  const { data } = await apiClient.get<ConfigOut>("/config")
  return data
}

export interface ImmichLinks {
  assetUrl: (assetId: string) => string
  personUrl: (personId: string) => string
  albumUrl: (albumId: string) => string
}

function linksFromBaseUrl(baseUrl: string): ImmichLinks {
  return {
    assetUrl: (assetId) => `${baseUrl}/photos/${assetId}`,
    personUrl: (personId) => `${baseUrl}/people/${personId}`,
    albumUrl: (albumId) => `${baseUrl}/albums/${albumId}`,
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
      .then(
        (config) =>
          (cached = config.immich_external_url
            ? linksFromBaseUrl(config.immich_external_url)
            : null),
      )
      .catch(() => (cached = null))
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
