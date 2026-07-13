import axios from "axios"

import { getOwnerId } from "./ownerId"

export const apiClient = axios.create({
  baseURL: "/api/v1",
})

apiClient.interceptors.request.use((config) => {
  config.headers["X-Owner-Id"] = getOwnerId()
  return config
})
