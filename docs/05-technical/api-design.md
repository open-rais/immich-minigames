# REST API Design

Base URL: `/api`

---

## Settings

### GET /api/settings

Retrieve current Immich connection settings.

**Response:**
```json
{
  "immich_url": "https://photos.example.com",
  "last_health_check": "2024-01-01T12:00:00Z"
}
```

---

### PUT /api/settings

Update Immich connection settings.

**Request:**
```json
{
  "immich_url": "https://photos.example.com",
  "immich_api_key": "secret_key_here"
}
```

---

### POST /api/settings/test-connection

Test the connection to Immich.

**Response:**
```json
{
  "success": true,
  "message": "Connected to Immich v1.102.0"
}
```

---

## Games

### GET /api/games

List all available games.

**Response:**
```json
[
  {
    "slug": "more-or-less",
    "name": "More or Less",
    "description": "Guess if next has more or less...",
    "modes": ["person-items", "album-items", "timeline"]
  }
]
```

---

### GET /api/games/{game}

Get details for a specific game.

---

### GET /api/games/{game}/{mode}

Get details for a game mode.

---

## Sessions

### POST /api/sessions/start

Start a new game session.

**Request:**
```json
{
  "game_slug": "more-or-less",
  "mode_slug": "person-items"
}
```

**Response:**
```json
{
  "session_id": "uuid-here",
  "game_slug": "more-or-less",
  "mode_slug": "person-items",
  "score": 0,
  "round_number": 1
}
```

---

### GET /api/sessions/{id}

Get current session state.

---

### GET /api/sessions/{id}/round

Get current round.

**Response:**
```json
{
  "round_number": 1,
  "prompt": "Person A has 42 items. Does Person B have more or less?",
  "metadata": {
    "person_a_name": "Alice",
    "person_a_count": 42
  }
}
```

---

### POST /api/sessions/{id}/answer

Submit an answer for the current round.

**Request:**
```json
{
  "answer": "more"
}
```

**Response:**
```json
{
  "correct": true,
  "points_awarded": 1,
  "current_score": 5,
  "game_over": false,
  "feedback": "Correct! Person B has 55 items."
}
```

---

### POST /api/sessions/{id}/finish

Finish the game session.

**Response:**
```json
{
  "final_score": 150,
  "best_score": 200,
  "summary": "Great game! You got 8/10 correct."
}
```

---

## Statistics

### GET /api/stats

Get global game statistics.

**Response:**
```json
{
  "games": [
    {
      "game_slug": "more-or-less",
      "modes": [
        {
          "mode_slug": "person-items",
          "best_score": 7,
          "times_played": 5
        }
      ]
    }
  ]
}
```

---

### GET /api/stats/{game}

Get statistics for a specific game.

---

## Error Handling

All errors follow a standard format:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {}
}
```

**Common error codes:**
- `SETTINGS_NOT_CONFIGURED` — Immich connection not set
- `IMMICH_CONNECTION_FAILED` — Cannot reach Immich
- `INVALID_SESSION` — Session expired or not found
- `INVALID_ANSWER` — Answer format incorrect
