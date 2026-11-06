// @vitest-environment jsdom
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import { TriviumBoard } from "./TriviumBoard"
import { questionSegments } from "./questionText"

const words = questionSegments("Who is **Ana?**")

function renderBoard(props: Partial<Parameters<typeof TriviumBoard>[0]> = {}) {
  return render(
    <TriviumBoard
      media={{ kind: "none" }}
      questionWords={words}
      hasPersonAlternatives={false}
      alternatives={<button type="button">Option</button>}
      {...props}
    />,
  )
}

describe("TriviumBoard", () => {
  it("keeps the alternatives laid out but hidden from assistive tech until they're up", () => {
    // Laid out (not unmounted) because their height is what the media sizes itself against.
    renderBoard({ alternativesUp: false })
    const block = screen.getByTestId("trivium-alternatives")
    expect(block.getAttribute("aria-hidden")).toBe("true")
    expect(block.style.opacity).toBe("0")
    expect(screen.queryByRole("button", { name: "Option" })).toBeNull()
  })

  it("shows the alternatives by default", () => {
    renderBoard()
    expect(screen.getByRole("button", { name: "Option" })).toBeTruthy()
    expect(screen.getByTestId("trivium-alternatives").style.opacity).toBe("1")
  })

  it("lays out every word of the question but only shows the revealed ones", () => {
    renderBoard({ revealedWordCount: 1 })
    const spans = screen.getByTestId("trivium-question").querySelectorAll("span")
    expect(spans).toHaveLength(words.length)
    expect(spans[0].className).toContain("opacity-100")
    expect(spans[spans.length - 1].className).toContain("opacity-0")
  })

  it("shows every word when no reveal count is given (the rounds review)", () => {
    renderBoard()
    const spans = screen.getByTestId("trivium-question").querySelectorAll("span")
    expect([...spans].every((s) => s.className.includes("opacity-100"))).toBe(true)
  })
})
