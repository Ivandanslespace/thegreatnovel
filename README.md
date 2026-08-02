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

**Phase 9C — Phase 9C1 frozen at `phase-9c1-frozen`; Phase 9C2 implementation candidate (not frozen)**

Accepted Phase 9C1 implementation SHA: `04640bb2bf8e9ab27980c9be61e8f89edf44bd28`。
Phase 9C1 freeze commit / `phase-9c1-frozen` target: `9bb739fdb1bd08d4c0c036e7c3d3c0ee5d083f01`。
`phase-9c1-frozen` is immutable and must never be moved, deleted, or recreated。
Initial Phase 9C2 implementation: `ad4772e6a712bfb445860b4e8daf8498a3cec363`。
Phase 9C2 conditional-replacement correction: `b5fa586fb7e0838a95e14fb445508f4b5d8a32e6`。
Phase 9C2 Windows/recovery correction: `5685fb645d30d85bf4942e91973409d878d97bac`。
Phase 9C2 cleanup identity correction: `0dc03156155a8914d586e6efb621c5817e0a05c7`；
Phase 9C2 recovery test correction: `d1f64153e59c3f62cd4784f0641b2cadda38f325`；
Phase 9C2 Windows delete-HANDLE exact-observable correction: `a445cf4b925f550d22c661504049be025ffa73c2`；
parallel pytest tooling commit: `1dfa3fe33bf5bea35e831cf56af9678fd2e88dd4`。
Phase 9C2 remains unfrozen; no `phase-9c2-frozen` tag exists。
Playable Client Milestone not started。
Phase 9D not started。

Phase 9C 的合同范围是 Persistent External Narration, Resume and Novel Export：
使用与 Campaign 分离的 immutable Story sidecar 保存 deterministic Narration Request、
pending/resume 状态和 committed turn artifacts，再从这些 artifact 确定性导出
novel.md。Phase 9C1 不包含 Narration provider、Narrator adapter、翻译数据库或
Phase 9C 以外的功能。Phase 9C2 candidate 增加 per-turn locale switching、
deterministic snapshot/final novel export、terminal completion metadata、novel
status classification 和 export CLI；不引入 provider、Story SQLite 或通用框架。
合同同时固定历史 snapshot 的自有导出边界、冻结
Session 的单 Event 基线和稳定 Campaign snapshot 捕获协议。当前实现覆盖
Campaign-bound Story persistence、deterministic Narration Request、pending/resume、
structured claims、committed turn artifacts、status、verify、local CLI、locale
switching 和 deterministic novel export；Phase 9C1 仍冻结，Phase 9C2 仍是
implementation candidate。

Phase 9C1 publication source-identity correction commit：`739a656fc8e7b50a12484049bb0f4598aa0cb1b2`；
final idempotent source-identity fix：`f5aeba6dd0e02a028dde8c077dd5c68dfbd98159`；
loaded Story directory identity fix：`04640bb2bf8e9ab27980c9be61e8f89edf44bd28`。
本次修复将 Story root、requests/ 和 turns/ 的 publication parent 锚定到已验证的
POSIX directory fd 或 Windows directory HANDLE；临时 artifact 的 retained
descriptor/HANDLE、当前 source-name identity 和发布 target identity 必须一致，
pending request 也通过已锚定的 requests/ binding 重新验证；Phase 9C1 已冻结在
`phase-9c1-frozen`。final fix 使 already-committed 重交也经过
Story root/turns identity、Campaign historical prefix 和 committed turn source
identity 的完整校验，并在 post-move target identity 不匹配时保留竞争者 target。
本次 directory fix 还要求 recommit 的 root/turns binding 与已加载 StoryView 的目录 identity 相等。
Phase 9C2 conditional-replacement correction：`b5fa586fb7e0838a95e14fb445508f4b5d8a32e6`。`novel.md` 的已有目标现在
必须以完整 expected observable 进行条件替换；POSIX 使用 anchored exchange 保留
displaced target，Windows 使用 `ReplaceFileW` 及 writer-owned backup；parent、target
和 writer artifact 在原子操作后再次校验，竞争者不会被覆盖或删除。CLI 的
`ReplaceFileW` 失败会保留精确的 `1175`、`1176` 和 `1177` outcome，并在 bound
Story parent 内重新检查 target、replacement、backup 与 retained writer HANDLE。
可证明的 `1177` partial layout 会先以 no-replace 恢复 expected target；未知对象
只会触发 bounded failure，不会被删除。POSIX displaced expected target 也只在
完整 observable 相等时清理，recoverable failure 不留下 `.tmp` 或 `.backup`。
`--accepted-decisions` 只接受 canonical non-negative integer。Phase 9C2 candidate
当前验证：Story `240 passed`、Story coverage `96.94%`；Campaign `173 passed, 2 skipped`、
Campaign coverage `97.55%`；Worldgen `150 passed`；Projection `112 passed`、Projection
coverage `100%`；Session `74 passed`；LLM Player `63 passed`；Phase 8 autoplay
`1 passed`；全仓 `1635 passed, 2 skipped`、全仓 coverage `97.04%`；warning-as-error
全仓回归为 `0 warnings`。使用 pytest-xdist `3.8.0`，12/12 worker、WorkStealing，
max-worker-restart=0，未发生 worker crash/restart。
两个 skipped 是 Windows 上
`tests/campaign/test_no_follow.py::test_campaign_fifo_is_rejected_on_posix` 和
`tests/campaign/test_no_follow.py::test_copy_fifo_source_is_rejected_on_posix`，原因是
当前平台无法创建 POSIX FIFO；不是 Phase 9C1 测试失败。

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
process. Phase 9C1 is frozen at `phase-9c1-frozen`; Phase 9C2 is an implementation
candidate and remains unfrozen.

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
`218a246add4481088872487e80ac83ad1099171b`. Phase 9C1 is frozen at
`phase-9c1-frozen`; Phase 9C2 is an implementation candidate and remains unfrozen.

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
