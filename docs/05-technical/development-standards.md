# Development Standards

## Code Quality Tools

### Python

#### Formatting
- **Black** - Code formatter
  - Line length: 100 characters
  - Enforced in pre-commit

#### Linting
- **Ruff** - Fast linter
  - Detects unused imports, undefined names, unused variables
  - Enforces PEP 8 style
  - Runs before commit

#### Type Checking
- **Mypy** - Static type checker
  - Strict mode enabled
  - All functions must have type hints
  - Optional parameters explicit

#### Import Organization
- **isort** - Import sorter
  - Integrated with Ruff
  - Sorts by category: stdlib, third-party, local

---

### TypeScript / Frontend

#### Formatting
- **Prettier** - Code formatter
  - Line length: 100 characters

#### Linting
- **ESLint** - JavaScript linter
  - React best practices
  - Next.js recommendations

#### Type Checking
- **TypeScript Strict Mode** - Static type safety
  - `strict: true`
  - No implicit any
  - Strict null checks

---

## Testing Strategy

### Unit Tests (Minimum)

Test individual functions/classes in isolation.

**Location:** `tests/unit/`

**Tools:** pytest

**Example:**
```python
def test_settings_repository_get():
    # Arrange
    # Act
    # Assert
```

---

### Integration Tests (Minimum)

Test interactions between layers (DB, API, etc).

**Location:** `tests/integration/`

**Tools:** pytest, pytest-asyncio

**Example:**
```python
async def test_settings_api_returns_configured_url():
    # Test actual DB + HTTP endpoint
```

---

### E2E Tests (Optional)

Test complete user workflows.

**Tools:** Playwright

**Example:**
```python
async def test_user_connects_to_immich_and_plays_game():
    # Test UI + API + DB integration
```

---

## Git Workflow

### Branching Strategy

```
main               # Production-ready
├── develop        # Integration branch
├── feature/*      # New features
├── fix/*          # Bug fixes
├── docs/*         # Documentation
└── refactor/*     # Code improvements
```

### Commit Messages

Follow Conventional Commits:

```
type(scope): subject

body (optional)

footer (optional)
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `refactor:` - Code refactoring
- `test:` - Adding/updating tests
- `chore:` - Maintenance tasks
- `ci:` - CI/CD changes

**Examples:**
```
feat(games): add MoreOrLess game plugin
fix(api): handle null settings gracefully
docs(architecture): update backend layers
test(settings): add repository unit tests
```

---

## Repository Standards

### Required Files

- `README.md` - Project overview
- `CONTRIBUTING.md` - Contribution guidelines
- `LICENSE` - Project license
- `CHANGELOG.md` - Version history
- `CODE_OF_CONDUCT.md` - Community guidelines
- `SECURITY.md` - Security reporting

### Code Organization

- **Consistent indentation** - 4 spaces (Python), 2 spaces (TS)
- **Meaningful names** - Clear, descriptive identifiers
- **Small functions** - Single responsibility
- **Comments** - Explain why, not what
- **Docstrings** - All public functions documented

---

## Pre-Commit Checks

The following run automatically before each commit:

1. ✅ Format code (Black)
2. ✅ Organize imports (isort)
3. ✅ Lint (Ruff)
4. ✅ Type check (Mypy)
5. ✅ Run tests (Pytest)

If any check fails, the commit is rejected. Fix and try again.

---

## Code Review Checklist

Before submitting a pull request:

- [ ] Code passes all linting checks
- [ ] Code is formatted with Black
- [ ] Type hints added for all functions
- [ ] Tests written (unit + integration)
- [ ] Tests pass locally
- [ ] Documentation updated if needed
- [ ] Commit messages follow convention
- [ ] No secrets or credentials in code
- [ ] CHANGELOG updated
