# MVP Scope

## Initial MVP Focus

The MVP will only implement the following:

- Settings system
- Immich connection
- MoreOrLess game
- person-items mode
- High score tracking

**Everything else comes later.**

---

## Architecture Decision Record (ADR)

### Decision: Modular Monolith Architecture

**Chosen architecture:** Modular monolith.

### Why Modular Monolith?

#### Benefits

- easier deployment
- simpler development
- plugin-ready
- scalable enough
- can evolve later

This approach provides a solid foundation while remaining flexible for future evolution into microservices if needed.
