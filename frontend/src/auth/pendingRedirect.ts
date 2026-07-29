// Roadmap #H, F0 (still used post-F3) - carries "where to go back to after logging in" between
// whichever of AuthProvider's global 401 interceptor / RequireAuth.tsx (App.tsx's centralized
// route guard) triggers the redirect to /login, and LoginPage, which consumes it after a
// successful login. Originally a plain module variable rather than react-router's own
// navigate(path, { state }) because F0-through-F2 had every protected page carrying its own
// `!user -> Navigate to /login` guard, and those raced with the interceptor's - RequireAuth (F3)
// replaced all of those with itself, removing the race, but this stayed the simpler mechanism
// (both places that redirect just call setPendingRedirectFrom first) rather than switching to
// state for no real benefit now.
let pendingFrom: string | null = null

export function setPendingRedirectFrom(path: string): void {
  pendingFrom = path
}

export function consumePendingRedirectFrom(): string | null {
  const from = pendingFrom
  pendingFrom = null
  return from
}
