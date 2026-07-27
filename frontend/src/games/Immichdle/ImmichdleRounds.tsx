import { GameType } from "../../api/types"
import type { ImmichdleRoundOut } from "../../api/types"
import type { RoundsComponentProps } from "../catalog"
import type { TargetSnapshot } from "./clueColors"
import { GuessTable } from "./GuessTable"

// The GuessTable as it stood at the end of a finished Immichdle game, plus the target row
// (ROUNDS-VIEW.md roadmap #10, §3 F/§4.6) - "list" family (registered with no roundsLayout in
// catalog.ts), so RoundsShell wraps this exactly as it does MoreOrLessRounds.
export function ImmichdleRounds({ game }: RoundsComponentProps) {
  // A round still pending an answer (a game reached mid-play by URL) is dropped, same convention
  // MoreOrLessRounds.tsx/GeoguessrRounds.tsx already established (§3 H). A won game's last guess
  // *is* the target - also dropped here, since the target row above already shows that same
  // person; keeping it in the history below would just show it twice.
  const history = game.rounds
    .filter((r): r is ImmichdleRoundOut => r.game_type === GameType.Immichdle)
    .filter((r) => r.guess_person_id !== null && !r.correct)

  // Only ever set for a finished Immichdle game (backend redacts it otherwise - see
  // api/dto/common.py's GameOut.from_game) - RoundsPage never reaches an unfinished game anyway.
  const target: TargetSnapshot | undefined =
    game.target_person_id && game.target_person_name
      ? {
          personId: game.target_person_id,
          name: game.target_person_name,
          assetCount: game.target_asset_count ?? 0,
          birthDate: game.target_birth_date ?? null,
          firstAssetDate: game.target_first_asset_date ?? null,
        }
      : undefined

  return (
    <div className="mx-auto w-full max-w-4xl">
      <GuessTable history={history} target={target} />
    </div>
  )
}
