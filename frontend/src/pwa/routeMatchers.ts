// Pure path matchers for src/sw.ts's cache routes - kept separate from sw.ts itself so they're
// testable without a ServiceWorkerGlobalScope (sw.ts's own top-level calls like skipWaiting()
// need the real worker global and can't be imported into a plain test).
export function isStaticAssetPath(pathname: string): boolean {
  return (
    pathname === "/logo.svg" ||
    pathname === "/apple-touch-icon.png" ||
    pathname.startsWith("/icon-") ||
    pathname.startsWith("/covers/")
  )
}

const THUMBNAIL_PATH_RE = /^\/api\/v1\/(people|assets|albums)\/[^/]+\/thumbnail$/

export function isThumbnailPath(pathname: string): boolean {
  return THUMBNAIL_PATH_RE.test(pathname)
}

export function isConfigPath(pathname: string): boolean {
  return pathname === "/api/v1/config"
}
