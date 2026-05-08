# Development Roadmap

## Phase Structure

Each phase has a priority level:
- **P0** - MVP critical path (Q1 2026)
- **P1** - MVP expansion (Q2 2026)
- **P2** - Enhanced features (Q3 2026+)

---

## Phase 0 - Foundation

**Priority:** P0

### Repository Setup
- [x] Initialize repository
- [ ] Configure backend environment
- [ ] Configure frontend environment
- [ ] Configure Docker Compose
- [ ] Setup environment management

### Tooling
- [ ] Configure linting (ruff)
- [ ] Configure formatting (black)
- [ ] Configure pre-commit hooks
- [ ] Configure CI pipeline (optional)

### Documentation
- [ ] README
- [ ] CONTRIBUTING
- [ ] Architecture docs

**Status:** In Progress  
**Estimated:** 1-2 weeks

---

## Phase 1 - Core Engine

**Priority:** P0

### Settings System
- [ ] Settings domain entity
- [ ] Settings database model
- [ ] Settings repository
- [ ] Settings API endpoints
- [ ] Settings UI
- [ ] Test connection endpoint

### Game Registry
- [ ] GameRegistry class
- [ ] Plugin registration system
- [ ] Dynamic game loading

### Session Engine
- [ ] Session creation
- [ ] Session retrieval
- [ ] Session cleanup (TTL)
- [ ] Redis integration

### Stats Engine
- [ ] GameStats entity and model
- [ ] High score tracking
- [ ] Games played tracking
- [ ] Stats API endpoints

**Status:** Not Started  
**Estimated:** 2-3 weeks

---

## Phase 2 - Immich Integration

**Priority:** P0

### Base API Client
- [ ] Immich HTTP client (httpx)
- [ ] Authentication handling
- [ ] Health endpoint
- [ ] Error handling and retry logic

### People API
- [ ] List people endpoint
- [ ] Random person selection
- [ ] Person asset count

### Albums API
- [ ] List albums endpoint
- [ ] Random album selection
- [ ] Album asset count

### Assets API
- [ ] List assets endpoint
- [ ] Random asset selection
- [ ] Asset metadata retrieval

**Status:** Not Started  
**Estimated:** 2 weeks

---

## Phase 3 - MoreOrLess MVP

**Priority:** P0

### Plugin Creation
- [ ] GamePlugin interface
- [ ] MoreOrLess plugin implementation
- [ ] Mode registration system

### person-items Mode
- [ ] Round generation logic
- [ ] Answer validation
- [ ] Scoring algorithm
- [ ] Tests

### Frontend UI
- [ ] Game selection page
- [ ] Round display page
- [ ] Answer submission
- [ ] Result page
- [ ] High score display

**Status:** Not Started  
**Estimated:** 2-3 weeks

---

## Phase 4 - MoreOrLess Expansion

**Priority:** P1

### album-items Mode
- [ ] Round generation
- [ ] Answer validation
- [ ] Scoring

### timeline Mode
- [ ] Date-based comparison
- [ ] Answer validation
- [ ] Scoring

**Status:** Not Started  
**Estimated:** 1 week

---

## Phase 5 - Geoguessr

**Priority:** P1

### Location Retrieval
- [ ] Get assets by location
- [ ] Location grouping logic

### Map Integration
- [ ] Map UI component
- [ ] Location selection

### Distance Scoring
- [ ] Distance calculation
- [ ] Score algorithm

**Status:** Not Started  
**Estimated:** 2 weeks

---

## Phase 6 - Dateguessr

**Priority:** P1

### Date Grouping
- [ ] Get assets by date
- [ ] Same-day grouping

### Timeline UI
- [ ] Timeline component
- [ ] Date selection interface

### Date Scoring
- [ ] Time difference calculation
- [ ] Score algorithm

**Status:** Not Started  
**Estimated:** 2 weeks

---

## Phase 7 - WhoIsThere

**Priority:** P2

### Face Detection
- [ ] Retrieve faces from Immich
- [ ] Face box extraction

### Blur Overlay
- [ ] Face masking UI
- [ ] Blur effect implementation

### Answer Validation
- [ ] Person matching logic
- [ ] Scoring

**Status:** Not Started  
**Estimated:** 2 weeks

---

## Phase 8 - Immichdle

**Priority:** P2

### Person Selection
- [ ] Random target person

### Hint Engine
- [ ] Age hints
- [ ] Item count hints
- [ ] Face similarity hints
- [ ] Shared appearance hints

**Status:** Not Started  
**Estimated:** 2-3 weeks

---

## Future Ideas

These are not in scope for initial release:

- Daily challenges
- Multiplayer support
- Global leaderboards
- Custom game settings
- Difficulty modes
- Community-made games
- Custom game creation UI

---

## Backlog Management

Issues are triaged by:
1. Priority (P0, P1, P2)
2. Phase (0-8)
3. Effort estimate (S, M, L)

New feature requests should include:
- Clear use case
- Which phase it belongs to
- Why it matters for target audience
