// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { AssetCarousel } from "./AssetCarousel"

describe("AssetCarousel", () => {
  it("renders no arrows for a single asset", () => {
    render(<AssetCarousel assetIds={["a"]} alt="" index={0} onIndexChange={vi.fn()} />)
    expect(screen.queryByLabelText("common.nextPhoto")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("common.previousPhoto")).not.toBeInTheDocument()
  })

  it("clicking next reports index + 1, without touching its own state", () => {
    const onIndexChange = vi.fn()
    render(<AssetCarousel assetIds={["a", "b", "c"]} alt="" index={0} onIndexChange={onIndexChange} />)

    fireEvent.click(screen.getByLabelText("common.nextPhoto"))

    expect(onIndexChange).toHaveBeenCalledWith(1)
  })

  it("clicking prev reports index - 1", () => {
    const onIndexChange = vi.fn()
    render(<AssetCarousel assetIds={["a", "b", "c"]} alt="" index={2} onIndexChange={onIndexChange} />)

    fireEvent.click(screen.getByLabelText("common.previousPhoto"))

    expect(onIndexChange).toHaveBeenCalledWith(1)
  })

  it("prev is disabled at index 0, next is disabled at the last index", () => {
    const { rerender } = render(
      <AssetCarousel assetIds={["a", "b"]} alt="" index={0} onIndexChange={vi.fn()} />,
    )
    expect(screen.getByLabelText("common.previousPhoto")).toBeDisabled()
    expect(screen.getByLabelText("common.nextPhoto")).not.toBeDisabled()

    rerender(<AssetCarousel assetIds={["a", "b"]} alt="" index={1} onIndexChange={vi.fn()} />)
    expect(screen.getByLabelText("common.previousPhoto")).not.toBeDisabled()
    expect(screen.getByLabelText("common.nextPhoto")).toBeDisabled()
  })

  it("the next arrow is inert at the last index, never reporting past the bounds", () => {
    const onIndexChange = vi.fn()
    render(<AssetCarousel assetIds={["a", "b"]} alt="" index={1} onIndexChange={onIndexChange} />)

    fireEvent.click(screen.getByLabelText("common.nextPhoto"))

    expect(onIndexChange).not.toHaveBeenCalled()
  })

  it("re-rendering with a new index shows that photo, driven entirely by the prop", () => {
    const { rerender } = render(
      <AssetCarousel assetIds={["a", "b"]} alt="alt text" index={0} onIndexChange={vi.fn()} />,
    )
    expect(screen.getByAltText("alt text")).toHaveAttribute("src", expect.stringContaining("a"))

    rerender(<AssetCarousel assetIds={["a", "b"]} alt="alt text" index={1} onIndexChange={vi.fn()} />)
    expect(screen.getByAltText("alt text")).toHaveAttribute("src", expect.stringContaining("b"))
  })
})
