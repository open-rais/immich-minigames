import { Suspense, useCallback, useEffect, useRef, useState } from "react"
import { Navigate, useParams } from "react-router-dom"

import { findCatalogMode } from "../games/catalog"
import { DailyFinishedContext } from "../games/shared/dailyFinishedContext"
import { DailyFollowUpModal } from "./DailyFollowUpModal"

// How long the finished screen (score + tip) is left alone before the follow-up modal covers it.
const FOLLOW_UP_DELAY_MS = 1500

// /daily/:gameType/:mode. Resolves through the same catalog as the normal
// menu/GameRoute.tsx and renders the exact same mode component, just with `daily` set - the
// component's own useRoundGame call is what actually changes behavior (see that hook).
//
// It also owns the "what now?" modal that opens once the player finishes today's daily: the game
// itself only reports *that* it finished (games/shared/dailyFinishedContext.ts), because deciding
// what to offer needs games/catalog.ts, which nothing in the game tree may import.
export function DailyGameRoute() {
  const { gameType, mode } = useParams<{ gameType: string; mode: string }>()
  const catalogMode = gameType && mode ? findCatalogMode(gameType, mode) : undefined
  const [followUpOpen, setFollowUpOpen] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleFinished = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setFollowUpOpen(true), FOLLOW_UP_DELAY_MS)
  }, [])

  // The modal navigates to another daily without unmounting this route, so a pending timer (or an
  // open modal) from the game just finished has to be dropped when the mode changes, not only on
  // unmount.
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = null
      setFollowUpOpen(false)
    }
  }, [gameType, mode])

  if (!catalogMode) return <Navigate to="/" replace />

  const Component = catalogMode.component
  return (
    <DailyFinishedContext.Provider value={handleFinished}>
      {/* catalog.ts's component is lazy-loaded (B-1) - this Suspense covers its chunk download. */}
      <Suspense fallback={<div className="min-h-dvh bg-app-bg" />}>
        <Component
          // Two modes of the same game share one component (MoreOrLess's two, Immichdle's two), so
          // jumping between dailies from the follow-up modal would otherwise keep the previous
          // mode's instance - and with it the finished game it was showing.
          key={`${gameType}/${mode}`}
          coverUrl={catalogMode.coverUrl}
          hasRoundsView={!!catalogMode.roundsComponent}
          daily
        />
      </Suspense>
      {followUpOpen && <DailyFollowUpModal onClose={() => setFollowUpOpen(false)} />}
    </DailyFinishedContext.Provider>
  )
}
