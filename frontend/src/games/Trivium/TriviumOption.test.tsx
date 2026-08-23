// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { TriviumOption } from "./TriviumOption"

describe("TriviumOption", () => {
  it("marks the pending option with a primary ring, distinct from idle", () => {
    render(<TriviumOption state="pending">Answer</TriviumOption>)
    const button = screen.getByRole("button", { name: "Answer" })
    expect(button.className).toContain("ring-primary")
    expect(button.className).toContain("border-primary")
  })

  it("idle has no ring", () => {
    render(<TriviumOption state="idle">Answer</TriviumOption>)
    expect(screen.getByRole("button", { name: "Answer" }).className).not.toContain("ring-primary")
  })

  it("calls onClick when enabled", () => {
    const onClick = vi.fn()
    render(
      <TriviumOption state="idle" onClick={onClick}>
        Answer
      </TriviumOption>,
    )
    fireEvent.click(screen.getByRole("button", { name: "Answer" }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it("disabled options ignore clicks", () => {
    const onClick = vi.fn()
    render(
      <TriviumOption state="pending" disabled onClick={onClick}>
        Answer
      </TriviumOption>,
    )
    fireEvent.click(screen.getByRole("button", { name: "Answer" }))
    expect(onClick).not.toHaveBeenCalled()
  })
})
