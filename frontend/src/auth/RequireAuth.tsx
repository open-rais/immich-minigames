import { Navigate, Outlet, useLocation } from "react-router-dom"

import { useAuth } from "./useAuth"
import { setPendingRedirectFrom } from "./pendingRedirect"

// Roadmap #H, F3 - the single centralized route guard, replacing every page's own
// `if (!loading && !user) return <Navigate to="/login" replace />` (see App.tsx, a layout route
// wrapping everything except /login, /signup, /reset-password). Backed by the same
// pendingRedirect.ts module AuthProvider.tsx's 401 interceptor already uses - now that this is the
// *only* place redirecting to /login, there's no longer a competing per-page guard to race against
// (see pendingRedirect.ts's own comment, updated alongside this).
export function RequireAuth() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return null
  if (!user) {
    setPendingRedirectFrom(location.pathname)
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}
