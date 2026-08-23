// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { GameType, Mode } from "../../api/types/common"
import type { GameOut } from "../../api/types/common"
import type { DateguessrRoundOut } from "../../api/types/dateguessr"
import { DateguessrRounds } from "./DateguessrRounds"

// Regression coverage for docs/TODO's "report the photo you're actually looking at" fix -
// AssetCarousel is now controlled (see its own docstring), and this is the component that used to
// always pass round.asset_ids[0] to ImmichLink/ReportMenuItem regardless of which photo the
// carousel was showing. Stubbed out entirely (not just their network calls) - this test only cares
// which `id` reaches them, not their own rendering/fetch/modal behavior.
vi.mock("../shared/ImmichLink", () => ({
  ImmichLink: ({ id }: { id: string }) => <div data-testid="immich-link-id">{id}</div>,
}))
vi.mock("../shared/ReportMenuItem", () => ({
  ReportMenuItem: ({ id }: { id: string }) => <div data-testid="report-id">{id}</div>,
}))

function makeRound(overrides: Partial<DateguessrRoundOut> = {}): DateguessrRoundOut {
  return {
    game_type: GameType.Dateguessr,
    id: "round-1",
    round_index: 1,
    asset_ids: ["asset-1", "asset-2"],
    guess_date: "2020-01-01",
    actual_date: "2020-01-01",
    days_off: 0,
    score_delta: 100,
    ...overrides,
  }
}

function makeGame(rounds: DateguessrRoundOut[]): GameOut {
  return {
    id: "game-1",
    type: GameType.Dateguessr,
    mode: Mode.DaysToDate,
    score: 100,
    finished: true,
    rounds,
  }
}

describe("DateguessrRounds", () => {
  it("reports/links the currently-shown photo, not always the first one", () => {
    const game = makeGame([makeRound({ asset_ids: ["asset-1", "asset-2"] })])
    render(<DateguessrRounds game={game} />)
    fireEvent.click(screen.getByLabelText("common.rounds.optionsMenu"))

    expect(screen.getByTestId("report-id")).toHaveTextContent("asset-1")
    expect(screen.getByTestId("immich-link-id")).toHaveTextContent("asset-1")

    fireEvent.click(screen.getByLabelText("common.nextPhoto"))

    expect(screen.getByTestId("report-id")).toHaveTextContent("asset-2")
    expect(screen.getByTestId("immich-link-id")).toHaveTextContent("asset-2")
  })

  it("resets to the first photo when the stepper moves to a different round", () => {
    const game = makeGame([
      makeRound({ id: "round-1", asset_ids: ["a1", "a2"] }),
      makeRound({ id: "round-2", asset_ids: ["b1", "b2"] }),
    ])
    render(<DateguessrRounds game={game} />)
    fireEvent.click(screen.getByLabelText("common.rounds.optionsMenu"))

    fireEvent.click(screen.getByLabelText("common.nextPhoto"))
    expect(screen.getByTestId("report-id")).toHaveTextContent("a2")

    fireEvent.click(screen.getByLabelText("common.nextRound"))

    expect(screen.getByTestId("report-id")).toHaveTextContent("b1")
  })
})
