import { Suspense } from "react"
import { Navigate, useParams } from "react-router-dom"

import { findCatalogMode } from "../games/catalog"

// /daily/:gameType/:mode. Resolves through the same catalog as the normal
// menu/GameRoute.tsx and renders the exact same mode component, just with `daily` set - the
// component's own useRoundGame call is what actually changes behavior (see that hook).
export function DailyGameRoute() {
  const { gameType, mode } = useParams<{ gameType: string; mode: string }>()
  const catalogMode = gameType && mode ? findCatalogMode(gameType, mode) : undefined

  if (!catalogMode) return <Navigate to="/" replace />

  const Component = catalogMode.component
  return (
    // catalog.ts's component is lazy-loaded (B-1) - this Suspense covers its chunk download.
    <Suspense fallback={<div className="min-h-dvh bg-app-bg" />}>
      <Component
        coverUrl={catalogMode.coverUrl}
        hasRoundsView={!!catalogMode.roundsComponent}
        daily
      />
    </Suspense>
  )
}
