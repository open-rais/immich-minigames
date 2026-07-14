import axios from "axios"

// The backend's own domain exceptions (main.py's _error_handler) always come back as
// {"detail": "..."} - surface that message when present (e.g. "email already registered")
// instead of a generic fallback, since it's meaningful UX on auth forms.
export function apiErrorMessage(err: unknown): string | undefined {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === "string") return detail
  }
  return undefined
}
