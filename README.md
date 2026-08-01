# TheGreatNovel MVP Rewrite

A **deterministic, event-sourced, replayable game simulation core** designed to be tested by scripted and LLM agents.

## Current Status

**Phase 7 — frozen at `phase-7-frozen`**

**Phase 7.5 — frozen at `phase-7.5-frozen`**

**Phase 8 — frozen at `phase-8-frozen`**

**Phase 9A — frozen at `phase-9a-frozen`**

**Phase 9B1 — frozen at `phase-9b1-frozen`**

**Phase 9B2A — frozen at `phase-9b2a-frozen`**

Frozen implementation SHA: `60ebf493ba90114c4f03048558e316ac07118ee2`

**Phase 9B2B — frozen at `phase-9b2b-frozen`**

Frozen implementation SHA: `218a246add4481088872487e80ac83ad1099171b`

**Phase 9C — design contract candidate / implementation not started**

Phase 9C 的合同范围是 Persistent External Narration, Resume and Novel Export：
使用与 Campaign 分离的 immutable Story sidecar 保存 deterministic Narration Request、
pending/resume 状态和 committed turn artifacts，再从这些 artifact 确定性导出
novel.md。Phase 9C 尚未实现，不包含 Narration provider、Narrator adapter、翻译
数据库或 Phase 9C 以外的功能。

This branch contains the first WorldPack's local Phase 7 permanent build-choice
slice and the frozen Phase 7.5 named actor, relationship, and knowledge slice.
slice. Phase 9A is frozen at `phase-9a-frozen` and covers only the minimal
external-client session protocol using a supplied canonical initial GameState.
Phase 9B1 is the frozen bounded World Draft compilation slice at
`phase-9b1-frozen`: it validates strict
JSON, binds one reviewed mechanics profile to a deterministic Compiled WorldPack,
materializes an initial GameState, runs a scripted bootstrap smoke test, and
publishes a verified compiled bundle. It does not create formal Campaigns,
SQLite sessions, or narration. The Phase 7 build effects remain the explicit
`window_runner`, `field_rest`, and `quick_rest` candidates only; none of these
phases introduces a general framework. Phase 9B2A is the frozen Player-Visible
Projection Map at `phase-9b2a-frozen`: it adds a supplemental display-label
draft, a detached deterministic presentation sidecar, a separate presentation
hash, and a verified four-file projection bundle without changing the canonical
Engine request or creating a Campaign, Session, SQLite database, or Narration
layer. Phase 9B2B is frozen at `phase-9b2b-frozen` and covers Atomic Campaign
Bootstrap and Projected Session Integration. A Campaign uses copied and locked
WorldPack, Projection, and Phase 9A Session artifacts. Phase 9B2B does not
include Narration, novel export, an LLM provider, translation, or any Phase 9C
functionality. Its frozen implementation SHA is
`218a246add4481088872487e80ac83ad1099171b`. Frozen implementation must not be
modified directly; any fix requires an explicit reopen or superseding-phase
process. Phase 9C is a design contract candidate / implementation not started.

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
frozen at `phase-9a-frozen`; Phase 9B1 is frozen at `phase-9b1-frozen`; Phase
9B2A is frozen at `phase-9b2a-frozen`; Phase 9B2B is frozen at
`phase-9b2b-frozen` with implementation SHA
`218a246add4481088872487e80ac83ad1099171b`. Phase 9C is a design contract
candidate / implementation not started.

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
