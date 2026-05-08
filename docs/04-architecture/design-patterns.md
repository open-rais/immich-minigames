# Design Patterns & SOLID Principles

## Design Patterns Used

### Strategy Pattern

**Purpose:** Different scoring algorithms

**Use case:** Each game mode can have different scoring strategies

---

### Factory Pattern

**Purpose:** Game instance creation

**Use case:** GameRegistry creates game instances based on slug

---

### Adapter Pattern

**Purpose:** Immich API integration

**Structure:**
```
integrations/
└── immich/
    ├── client.py       # Low-level HTTP client
    ├── provider.py     # Adapter interface
    ├── mapper.py       # DTO mapping
    └── schemas.py      # Data structures
```

---

### Repository Pattern

**Purpose:** Data persistence abstraction

**Use case:** Settings and GameStats repositories decouple storage from business logic

---

### Template Method

**Purpose:** Game lifecycle template

**Use case:** GamePlugin defines the method skeleton, subclasses implement specific steps

---

### Dependency Injection

**Purpose:** Loose coupling between layers

**Use case:** Repositories, services, and adapters are injected, not instantiated

---

## SOLID Principles

### Single Responsibility Principle

Each module has one reason to change.

- `SettingsRepository` -> manages Settings persistence
- `ImmichClient` -> handles Immich API communication
- `MoreOrLessGame` -> implements MoreOrLess game logic

---

### Open/Closed Principle

Open for extension, closed for modification.

- New games added without modifying core engine
- New scoring strategies without changing GamePlugin
- New Immich endpoints without changing existing code

---

### Liskov Substitution Principle

Subtypes must be substitutable for their base types.

- All game plugins interchangeable (implement GamePlugin)
- All repositories follow same interface
- Any Immich version supported through adapter

---

### Interface Segregation Principle

Clients depend on small, focused interfaces.

- ImmichProvider split by capability (People, Albums, Assets, etc.)
- Repository interfaces only expose needed methods
- GamePlugin defines minimal essential contract

---

### Dependency Inversion Principle

High-level modules depend on abstractions, not low-level modules.

```
Application Layer (high-level)
         ↓
    Interfaces (abstractions)
         ↑
Infrastructure Layer (low-level)
```

**Example:**
- Application depends on `ImmichProvider` interface
- Infrastructure implements `ImmichProvider` with actual client
- Application never knows implementation details
