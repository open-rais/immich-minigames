import axios from "axios"

import { getOwnerId } from "./ownerId"

export const apiClient = axios.create({
  baseURL: "/api/v1",
  // A hung backend must not leave the UI stuck in `busy` forever (button disabled, no feedback).
  // Matches the backend's own 10s cap on its Immich calls; each screen's catch turns this into the
  // error/retry screen.
  timeout: 10000,
})

apiClient.interceptors.request.use((config) => {
  config.headers["X-Owner-Id"] = getOwnerId()
  return config
})
