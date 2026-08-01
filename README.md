# TheGreatNovel MVP Rewrite

A **deterministic, event-sourced, replayable game simulation core** designed to be tested by scripted and LLM agents.

## Current Status

**Phase 7 — frozen at `phase-7-frozen`**

**Phase 7.5 — frozen at `phase-7.5-frozen`**

**Phase 8 — frozen at `phase-8-frozen`**

**Phase 9A — frozen at `phase-9a-frozen`**

**Phase 9B1 — implementation candidate**

This branch contains the first WorldPack's local Phase 7 permanent build-choice
slice and the frozen Phase 7.5 named actor, relationship, and knowledge slice.
slice. Phase 9A is frozen at `phase-9a-frozen` and covers only the minimal
external-client session protocol using a supplied canonical initial GameState.
Phase 9B1 is the bounded World Draft compilation candidate: it validates strict
JSON, binds one reviewed mechanics profile to a deterministic Compiled WorldPack,
materializes an initial GameState, runs a scripted bootstrap smoke test, and
publishes a verified compiled bundle. It does not create formal Campaigns,
SQLite sessions, or narration. The Phase 7 build effects remain the explicit
`window_runner`, `field_rest`, and `quick_rest` candidates only; none of these
phases introduces a general framework.

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

Phases 1–6 establish the deterministic core, action validation, replay and
the first gameplay slices. Phase 7 is frozen at `phase-7-frozen`; Phase 7.5 is
frozen at `phase-7.5-frozen`; Phase 8 is frozen at `phase-8-frozen`; Phase 9A is
frozen at `phase-9a-frozen`; Phase 9B1 is the current implementation candidate.

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

- [DESIGN_VALUES.md](docs/DESIGN_VALUES.md) - Core design philosophy
- [MVP_REWRITE_SPEC.md](docs/MVP_REWRITE_SPEC.md) - Detailed architecture specification
- [DEFERRED.md](docs/DEFERRED.md) - Features explicitly out of scope

## License

See LICENSE file (if applicable).
