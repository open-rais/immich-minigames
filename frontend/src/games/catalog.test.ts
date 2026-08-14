import { describe, expect, it } from "vitest"
import { GameType, Mode } from "../api/types/common"
import { ALBUM_CLUE_COLUMNS } from "./Immichdle/albumGuessTableColumns"
import { CLUE_COLUMNS } from "./Immichdle/guessTableColumns"
import { MODE_CONFIG } from "./MoreOrLess/modeConfig"
import { GAME_CATALOG, findCatalogMode } from "./catalog"

// These four modules are configuration tables rather than logic, and tsc already checks their
// shape - what it cannot check is that the i18n keys they point at actually exist, or that no two
// entries collide. That is all this file does.

const locales = ["en", "es", "fr", "de"] as const

async function keysOf(locale: (typeof locales)[number]): Promise<Set<string>> {
  const bundle = (await import(`../i18n/locales/${locale}.json`)) as {
    default: Record<string, unknown>
  }
  const flat = new Set<string>()
  const walk = (node: Record<string, unknown>, prefix: string) => {
    for (const [key, value] of Object.entries(node)) {
      const path = prefix ? `${prefix}.${key}` : key
      if (value !== null && typeof value === "object") walk(value as Record<string, unknown>, path)
      else flat.add(path)
    }
  }
  walk(bundle.default, "")
  return flat
}

// i18next resolves a plural key ("x_one"/"x_other") from its base name, so a base that is missing
// but pluralized counts as present.
function has(keys: Set<string>, key: string) {
  return keys.has(key) || keys.has(`${key}_one`) || keys.has(`${key}_other`)
}

describe("i18n keys", () => {
  it("exist in English for every catalog game and mode", async () => {
    const keys = await keysOf("en")
    for (const game of GAME_CATALOG) {
      expect(has(keys, game.gameTitleKey), game.gameTitleKey).toBe(true)
      for (const mode of game.modes) {
        expect(has(keys, mode.modeTitleKey), mode.modeTitleKey).toBe(true)
      }
    }
  })

  it("exist in English for every MoreOrLess mode config", async () => {
    const keys = await keysOf("en")
    for (const [mode, cfg] of Object.entries(MODE_CONFIG)) {
      for (const key of [
        cfg.modeTitleKey,
        cfg.descriptionKey,
        cfg.hasLabelKey,
        cfg.questionKey,
        cfg.primaryLabelKey,
        cfg.secondaryLabelKey,
      ]) {
        expect(has(keys, key), `${mode}: ${key}`).toBe(true)
      }
    }
  })

  it("exist in English for every Immichdle and Albumdle clue column", async () => {
    const keys = await keysOf("en")
    for (const column of [...CLUE_COLUMNS, ...ALBUM_CLUE_COLUMNS]) {
      expect(has(keys, column.labelKey), column.labelKey).toBe(true)
    }
  })

  it("are the same set in all four languages", async () => {
    // Not about the catalog specifically: it is what stops a key added to en.json from silently
    // rendering as a raw key id for anyone playing in another language.
    const en = await keysOf("en")
    for (const locale of locales.filter((l) => l !== "en")) {
      const other = await keysOf(locale)
      expect(
        [...en].filter((k) => !other.has(k)),
        `missing in ${locale}`,
      ).toEqual([])
      expect(
        [...other].filter((k) => !en.has(k)),
        `extra in ${locale}`,
      ).toEqual([])
    }
  })
})

describe("the catalog", () => {
  it("lists every implemented game exactly once", () => {
    const types = GAME_CATALOG.map((g) => g.gameType)
    expect(new Set(types).size).toBe(types.length)
    expect(new Set(types)).toEqual(new Set(Object.values(GameType)))
  })

  it("has no duplicate game type and mode pair", () => {
    const pairs = GAME_CATALOG.flatMap((g) => g.modes.map((m) => `${g.gameType}/${m.mode}`))
    expect(new Set(pairs).size).toBe(pairs.length)
  })

  it("uses only known mode identifiers", () => {
    const known = new Set<string>(Object.values(Mode))
    for (const game of GAME_CATALOG) {
      for (const mode of game.modes) {
        expect(known.has(mode.mode), `${game.gameType}/${mode.mode}`).toBe(true)
      }
    }
  })

  it("only marks a rounds layout on modes that actually have a rounds view", () => {
    for (const game of GAME_CATALOG) {
      for (const mode of game.modes) {
        if (mode.roundsLayout)
          expect(mode.roundsComponent, `${game.gameType}/${mode.mode}`).toBeDefined()
      }
    }
  })

  it("finds a registered mode and nothing else", () => {
    expect(findCatalogMode(GameType.MoreOrLess, Mode.PersonAssets)?.mode).toBe(Mode.PersonAssets)
    expect(findCatalogMode(GameType.MoreOrLess, Mode.DaysToDate)).toBeUndefined()
    expect(findCatalogMode("nope", Mode.PersonAssets)).toBeUndefined()
  })
})

describe("MoreOrLess mode config", () => {
  it("covers exactly the modes the catalog offers", () => {
    const catalogModes = GAME_CATALOG.find((g) => g.gameType === GameType.MoreOrLess)!.modes.map(
      (m) => m.mode,
    )
    expect(Object.keys(MODE_CONFIG).sort()).toEqual([...catalogModes].sort())
  })

  it("agrees with the catalog on each mode's title key", () => {
    for (const mode of GAME_CATALOG.find((g) => g.gameType === GameType.MoreOrLess)!.modes) {
      expect(MODE_CONFIG[mode.mode].modeTitleKey).toBe(mode.modeTitleKey)
    }
  })

  it("sends a different guess on each of the two buttons", () => {
    for (const [mode, cfg] of Object.entries(MODE_CONFIG)) {
      expect(["more", "less"], mode).toContain(cfg.primaryGuess)
      expect(cfg.primaryLabelKey, mode).not.toBe(cfg.secondaryLabelKey)
    }
  })
})

describe("clue column tables", () => {
  it("has no duplicate column key", () => {
    for (const table of [CLUE_COLUMNS, ALBUM_CLUE_COLUMNS]) {
      const keys = table.map((c) => c.key)
      expect(new Set(keys).size).toBe(keys.length)
    }
  })

  it("has no duplicate label key", () => {
    for (const table of [CLUE_COLUMNS, ALBUM_CLUE_COLUMNS]) {
      const labels = table.map((c) => c.labelKey)
      expect(new Set(labels).size).toBe(labels.length)
    }
  })
})
