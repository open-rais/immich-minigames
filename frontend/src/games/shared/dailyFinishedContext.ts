import { createContext, useContext } from "react"

// "The player just finished today's daily" signal, from useGameSession (which is the only place
// that knows a daily ended by an actual guess, and not by re-opening an already-played one) up to
// menu/DailyGameRoute.tsx (which opens the follow-up modal).
//
// A context rather than a prop threaded through every *Game.tsx: the finished screen lives in
// games/shared/GameScreens.tsx, and the modal needs games/catalog.ts for each pending mode's title
// and cover - an import that module deliberately doesn't make (see its useRoundsHref comment). The
// context itself stays free of that import, so nothing in the game tree gains a catalog dependency.
//
// Null outside /daily/... (no provider) - every normal game calls the notifier and nothing happens.
export const DailyFinishedContext = createContext<(() => void) | null>(null)

export function useDailyFinishedNotifier(): (() => void) | null {
  return useContext(DailyFinishedContext)
}
