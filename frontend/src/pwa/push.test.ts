import { describe, expect, it } from "vitest"
import { urlBase64ToUint8Array } from "./push"

describe("urlBase64ToUint8Array", () => {
  it("decodes a base64url string with no padding needed", () => {
    // "hello" in base64 is "aGVsbG8=" - base64url strips the padding.
    const bytes = urlBase64ToUint8Array("aGVsbG8")
    expect(Array.from(bytes)).toEqual([104, 101, 108, 108, 111])
  })

  it("decodes a base64url string that needs padding restored", () => {
    // "hi" -> base64 "aGk=" -> base64url "aGk" (needs two '=' of padding restored to decode).
    const bytes = urlBase64ToUint8Array("aGk")
    expect(Array.from(bytes)).toEqual([104, 105])
  })

  it("converts '-' and '_' back to the standard base64 alphabet's '+' and '/'", () => {
    // Byte sequence chosen so standard base64 encoding actually produces '+' and '/':
    // 0xfb 0xff 0xbf -> base64 "+/+/", base64url "-_-_".
    const bytes = urlBase64ToUint8Array("-_-_")
    expect(Array.from(bytes)).toEqual([0xfb, 0xff, 0xbf])
  })

  it("round-trips a realistic-length VAPID public key", () => {
    const original = new Uint8Array(65)
    for (let i = 0; i < original.length; i++) original[i] = i * 4
    const base64Url = btoa(String.fromCharCode(...original))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "")

    expect(Array.from(urlBase64ToUint8Array(base64Url))).toEqual(Array.from(original))
  })
})
