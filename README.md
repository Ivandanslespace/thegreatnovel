# TheGreatNovel MVP Rewrite

A **deterministic, event-sourced, replayable game simulation core** designed to be tested by scripted and LLM agents.

## Current Status

**Phase 0 — Clean MVP workspace**

This is the initial cleanup phase. The core systems are being built from scratch:
- Game state management
- Event sourcing and replay
- Deterministic action resolution
- Agent testing infrastructure

## Legacy Implementation

The previous implementation is preserved for reference:
- Branch: `legacy/2026-07-31`
- Tag: `legacy-engine-2026-07-31`

**Do not modify these references.** They are read-only documentation of the legacy engine.

## Architecture Principles

1. **State First**: All game facts live in deterministic state
2. **Events as Truth**: Every change is recorded as an immutable event
3. **Replayability**: Any state can be reconstructed from events
4. **Agent Testing**: Designed for automated testing by scripted/LLM agents
5. **Minimal Core**: No abstractions for unimplemented features

## Development Phases

### Phase 0: Clean Workspace (Current)
- Basic Python package structure
- Test infrastructure setup

### Phase 1: Core Engine
- GameState
- Event types
- Reducer/apply_event
- Snapshot system

### Phase 2: Action System
- Action validation
- Deterministic resolution
- Time cost handling

### Phase 3: Autoplay Testing
- Scripted agent policies
- Random policy baseline
- Telemetry collection

### Future Phases
Will be defined as Phase 1 work progresses.

## Getting Started

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# Run tests
python -m pytest

# Run a test world
python -m tgn.demo  # (TBD in Phase 1)
```

## Documentation

- [DESIGN_VALUES.md](./DESIGN_VALUES.md) - Core design philosophy
- [MVP_REWRITE_SPEC.md](./MVP_REWRITE_SPEC.md) - Detailed architecture specification
- [DEFERRED.md](./DEFERRED.md) - Features explicitly out of scope

## License

See LICENSE file (if applicable).
