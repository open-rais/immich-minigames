import { describe, expect, it } from "vitest"

import { ReportEntity, ReportReason } from "../../api/types/reports"
import { REASONS_FOR_KIND, reasonLabelKey } from "./reportReasons"

describe("REASONS_FOR_KIND", () => {
  it("lists the three person reasons", () => {
    expect(REASONS_FOR_KIND[ReportEntity.Person]).toEqual([
      ReportReason.PersonBirthDate,
      ReportReason.PersonNameFaceMismatch,
      ReportReason.PersonNameSpelling,
    ])
  })

  it("lists the two album reasons", () => {
    expect(REASONS_FOR_KIND[ReportEntity.Album]).toEqual([
      ReportReason.AlbumCoverMismatch,
      ReportReason.AlbumNameSpelling,
    ])
  })

  it("lists the three asset reasons", () => {
    expect(REASONS_FOR_KIND[ReportEntity.Asset]).toEqual([
      ReportReason.AssetLocation,
      ReportReason.AssetDate,
      ReportReason.AssetFaceMismatch,
    ])
  })
})

describe("reasonLabelKey", () => {
  it("builds the i18n key under reports.reasons", () => {
    expect(reasonLabelKey(ReportReason.AssetDate)).toBe("reports.reasons.asset_date")
  })
})
