import { AxiosError, AxiosHeaders } from "axios"
import type { AxiosResponse } from "axios"
import { describe, expect, it } from "vitest"
import { apiErrorMessage, apiErrorStatus } from "./errors"

// The one place in the suite where axios itself is exercised rather than mocked - these two
// helpers exist precisely to recognize an AxiosError, so a hand-rolled fake would test nothing.
function axiosErrorWith(status: number, data: unknown): AxiosError {
  const config = { headers: new AxiosHeaders() }
  const response = {
    status,
    statusText: "",
    data,
    headers: {},
    config,
  } as AxiosResponse
  return new AxiosError("request failed", "ERR_BAD_REQUEST", config, {}, response)
}

// A request that never got a response at all (DNS failure, offline, CORS) - no `response` field.
function networkError(): AxiosError {
  return new AxiosError(
    "Network Error",
    AxiosError.ERR_NETWORK,
    { headers: new AxiosHeaders() },
    {},
  )
}

describe("apiErrorMessage", () => {
  it("surfaces the backend's own detail string", () => {
    expect(apiErrorMessage(axiosErrorWith(409, { detail: "email already registered" }))).toBe(
      "email already registered",
    )
  })

  it("ignores a non-string detail, such as FastAPI's validation error list", () => {
    const validationDetail = [{ loc: ["body", "email"], msg: "field required", type: "missing" }]
    expect(apiErrorMessage(axiosErrorWith(422, { detail: validationDetail }))).toBeUndefined()
  })

  it("returns undefined when the response body has no detail", () => {
    expect(apiErrorMessage(axiosErrorWith(500, {}))).toBeUndefined()
    expect(apiErrorMessage(axiosErrorWith(500, null))).toBeUndefined()
  })

  it("returns undefined for a network error with no response", () => {
    expect(apiErrorMessage(networkError())).toBeUndefined()
  })

  it("returns undefined for things that are not axios errors", () => {
    expect(apiErrorMessage(new Error("boom"))).toBeUndefined()
    expect(apiErrorMessage(null)).toBeUndefined()
    expect(apiErrorMessage(undefined)).toBeUndefined()
    expect(apiErrorMessage("just a string")).toBeUndefined()
    expect(apiErrorMessage({ detail: "looks like one but isn't" })).toBeUndefined()
  })
})

describe("apiErrorStatus", () => {
  it("returns the HTTP status of a failed response", () => {
    // The branch the daily flow depends on: 409 "already played today" is a state, not an error.
    expect(apiErrorStatus(axiosErrorWith(409, {}))).toBe(409)
    expect(apiErrorStatus(axiosErrorWith(401, {}))).toBe(401)
  })

  it("returns undefined for a network error that never got a response", () => {
    expect(apiErrorStatus(networkError())).toBeUndefined()
  })

  it("returns undefined for things that are not axios errors", () => {
    expect(apiErrorStatus(new Error("boom"))).toBeUndefined()
    expect(apiErrorStatus(null)).toBeUndefined()
  })
})
