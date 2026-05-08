# Domain Model

## Persistent Entities

### Settings

Configuration for Immich connection.

```
Settings
├── key: str (primary key)
├── value: str
└── updated_at: datetime
```

**Usage:** Stores immich_url and immich_api_key

---

### GameStats

High score tracking per game and mode.

```
GameStats
├── game_slug: str
├── mode_slug: str
├── best_score: int
└── times_played: int
```

**Usage:** Persistent game statistics

---

## Ephemeral Entities

### GameSession

Active game session (stored in Redis).

```
GameSession
├── id: str (uuid)
├── game_slug: str
├── mode_slug: str
├── score: int
├── round_number: int
└── state: dict
```

**Usage:** Tracks in-progress game

---

### GameRound

Current round in a game session.

```
GameRound
├── id: str
├── prompt: str
├── metadata: dict
```

**Usage:** Question/challenge data

---

### RoundResult

Evaluation of a player's answer.

```
RoundResult
├── correct: bool
├── points_awarded: int
├── current_score: int
├── game_over: bool
└── feedback: str
```

**Usage:** Immediate feedback to player

---

### GameResult

Final game outcome.

```
GameResult
├── final_score: int
├── best_score: int
└── summary: str
```

**Usage:** End-of-game statistics

---

## Plugin System

### GamePlugin Interface

Every game implements this contract.

```python
class GamePlugin:
    def start() -> GameSession
    def generate_round() -> GameRound
    def submit_answer(answer: Any) -> RoundResult
    def is_finished() -> bool
    def finalize() -> GameResult
```

---

### Game Registry

Manages plugin registration and lookup.

```python
class GameRegistry:
    def register(game_slug: str, plugin: GamePlugin)
    def get(game_slug: str) -> GamePlugin
```

**Purpose:** Dynamic plugin loading and management

---

## Game Lifecycle

```
Start Game
    ↓
Generate Round
    ↓
Receive Answer
    ↓
Validate Answer
    ↓
Calculate Score
    ↓
Next Round?
    ├─ YES → Generate Round
    └─ NO → Finalize & Return Results
```
