import { Navigate, useParams } from "react-router-dom"

import { findCatalogMode } from "../games/catalog"

// Resolves the /:gameType/:mode URL against the catalog and renders that mode's game component.
// An unknown/stale gameType+mode (typo'd URL, a mode that got removed) just bounces back to the
// menu instead of a dedicated 404 page.
export function GameRoute() {
  const { gameType, mode } = useParams<{ gameType: string; mode: string }>()
  const catalogMode = gameType && mode ? findCatalogMode(gameType, mode) : undefined

  if (!catalogMode) return <Navigate to="/" replace />

  const Component = catalogMode.component
  return <Component />
}
