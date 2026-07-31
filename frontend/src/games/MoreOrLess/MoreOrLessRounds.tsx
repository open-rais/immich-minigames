import { useParams } from "react-router-dom"

import { GameType, Mode } from "../../api/types"
import type { MoreOrLessRoundOut } from "../../api/types"
import type { RoundsComponentProps } from "../catalog"
import { EntryOptionsMenu } from "../shared/EntryOptionsMenu"
import { ImmichLink } from "../shared/ImmichLink"
import { PersonAvatar } from "../shared/PersonAvatar"
import { MODE_CONFIG } from "./modeConfig"

type ChainVariant = "neutral" | "correct" | "incorrect"

interface ChainEntry {
  id: string
  name: string
  assetCount: number
  variant: ChainVariant
}

// Only the count changes color - the card itself always keeps the same neutral, in-game style
// (StatCard.tsx's own border-line/bg-surface/shadow-card) regardless of variant, matching
// CandidateCard.tsx's existing reveal convention ("Only the number itself changes color on
// reveal - the card border/badge stay neutral").
const COUNT_COLOR_CLASS: Record<ChainVariant, string> = {
  neutral: "text-ink",
  correct: "text-clue-match",
  incorrect: "text-clue-miss",
}

// The chain of entities the player walked through: [round[0].reference, ...rounds.map(candidate)],
// colored by the round that had it as its candidate (ROUNDS-VIEW.md §4.6) - the first entry was
// never guessed, so it stays neutral. A round still pending an answer (a game reached mid-play by
// URL) is dropped first: its candidate never got a score, so it can't take a place in the chain.
function buildChain(rounds: MoreOrLessRoundOut[]): ChainEntry[] {
  const answered = rounds.filter((r) => r.candidate_asset_count !== null)
  if (answered.length === 0) return []

  const chain: ChainEntry[] = [
    {
      id: answered[0].reference_id,
      name: answered[0].reference_name,
      assetCount: answered[0].reference_asset_count,
      variant: "neutral",
    },
  ]
  for (const round of answered) {
    chain.push({
      id: round.candidate_id,
      name: round.candidate_name,
      assetCount: round.candidate_asset_count as number,
      variant: round.correct ? "correct" : "incorrect",
    })
  }
  return chain
}

export function MoreOrLessRounds({ game }: RoundsComponentProps) {
  const { mode = Mode.PersonAssets } = useParams<{ mode: string }>()
  const config = MODE_CONFIG[mode] ?? MODE_CONFIG[Mode.PersonAssets]
  const rounds = game.rounds.filter(
    (r): r is MoreOrLessRoundOut => r.game_type === GameType.MoreOrLess,
  )
  const chain = buildChain(rounds)

  return (
    <ol className="mx-auto flex w-full max-w-md flex-col gap-2">
      {chain.map((entry, index) => (
        <li
          key={`${entry.id}-${index}`}
          className="flex items-center gap-3 rounded-2xl border border-line bg-surface px-3 py-2 shadow-card"
        >
          <PersonAvatar src={config.thumbnailUrl(entry.id)} alt="" />
          <span className="line-clamp-2 min-w-0 flex-1 font-semibold text-ink">{entry.name}</span>
          <span className={`flex-none font-mono font-bold ${COUNT_COLOR_CLASS[entry.variant]}`}>
            {entry.assetCount}
          </span>
          <EntryOptionsMenu>
            <ImmichLink kind={config.linkKind} id={entry.id} />
          </EntryOptionsMenu>
        </li>
      ))}
    </ol>
  )
}
