import axios from "axios"

// Roadmap #H, F0 - lets a specific call opt out of AuthProvider.tsx's global 401-redirect
// interceptor (auth.ts's login/getMe: a 401 there is normal control flow, not an expired session).
declare module "axios" {
  export interface AxiosRequestConfig {
    skipAuthRedirect?: boolean
  }
}

export const apiClient = axios.create({
  baseURL: "/api/v1",
  // A hung backend must not leave the UI stuck in `busy` forever (button disabled, no feedback).
  // Matches the backend's own 10s cap on its Immich calls; each screen's catch turns this into the
  // error/retry screen.
  timeout: 10000,
})
