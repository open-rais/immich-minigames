// Roadmap #H, F0 - carries "where to go back to after logging in" between AuthProvider's global
// 401 interceptor and LoginPage. Deliberately a plain module variable, not react-router's
// navigate(path, { state }): every existing protected page still has its own
// `if (!loading && !user) return <Navigate to="/login" replace />` guard (pre-F3's centralized
// RequireAuth), which also fires once the interceptor clears `user` and re-navigates to /login
// itself, without state - overwriting whatever state the interceptor's own navigate call set.
// A module variable survives that race since it isn't tied to a specific history entry.
let pendingFrom: string | null = null

export function setPendingRedirectFrom(path: string): void {
  pendingFrom = path
}

export function consumePendingRedirectFrom(): string | null {
  const from = pendingFrom
  pendingFrom = null
  return from
}
