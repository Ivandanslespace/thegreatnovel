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

**Phase 9C — Phase 9C1 frozen at `phase-9c1-frozen`; Phase 9C2 frozen at `phase-9c2-frozen`**

Accepted Phase 9C1 implementation SHA: `04640bb2bf8e9ab27980c9be61e8f89edf44bd28`。
Phase 9C1 freeze commit / `phase-9c1-frozen` target: `9bb739fdb1bd08d4c0c036e7c3d3c0ee5d083f01`。
`phase-9c1-frozen` is immutable and must never be moved, deleted, or recreated。
Initial Phase 9C2 implementation: `ad4772e6a712bfb445860b4e8daf8498a3cec363`。
Phase 9C2 conditional-replacement correction: `b5fa586fb7e0838a95e14fb445508f4b5d8a32e6`。
Phase 9C2 Windows/recovery correction: `5685fb645d30d85bf4942e91973409d878d97bac`。
Phase 9C2 cleanup identity correction: `0dc03156155a8914d586e6efb621c5817e0a05c7`；
Phase 9C2 recovery test correction: `d1f64153e59c3f62cd4784f0641b2cadda38f325`；
Phase 9C2 Windows delete-HANDLE exact-observable correction: `a445cf4b925f550d22c661504049be025ffa73c2`；
Phase 9C2 Windows DELETE-HANDLE share-compatibility correction: `f9a8a10adb7579fe4e06e462fbbeee47cdf69aea`；
parallel pytest tooling commit: `1dfa3fe33bf5bea35e831cf56af9678fd2e88dd4`。
Accepted frozen Phase 9C2 implementation SHA: `f9a8a10adb7579fe4e06e462fbbeee47cdf69aea`。
`phase-9c2-frozen` is immutable and must never be moved, deleted, or recreated；
任何未来修复都必须经过显式 reopen 或 superseding-phase 流程。
Phase 9C2 frozen at `phase-9c2-frozen`。
Playable Client Milestone PC1 — frozen at `pc1-frozen`

Accepted PC1 implementation SHA: `96ffe3eefa9ea6558e3f9105f0a5a47838e3a1ce`。
`pc1-frozen` is immutable and must never be moved, deleted, or recreated。
Phase 9C2 remains frozen；Phase 9D deferred / not started。
main publishes the frozen PC1 baseline；mvp-rewrite carries the Phase 10A
implementation candidate and its documentation。Phase 10 documentation direction is
established；Phase 10A Feature Contract is locked as an implementation candidate；
Phase 10A production implementation candidate is recorded below，and Phase 10 remains
unfrozen。

Playable Client Milestone PC1 是 Phase 9C2 之上的薄本地产品整合层，现已冻结在
`pc1-frozen`。它只通过 Campaign 与 Story 的公开 service
API 组合一个可恢复的本地人类玩家 / 外部 narrator loop：Engine 先持久化一个
action，Story 再准备并提交 narration，只有 committed turn 才能向玩家显示 prose，
最终由 Story 导出 novel.md。PC1 不修改任何 frozen package、测试或配置，不开始
Phase 9D 或 Phase 10。

Phase 9C 的合同范围是 Persistent External Narration, Resume and Novel Export：
使用与 Campaign 分离的 immutable Story sidecar 保存 deterministic Narration Request、
pending/resume 状态和 committed turn artifacts，再从这些 artifact 确定性导出
novel.md。Phase 9C1 不包含 Narration provider、Narrator adapter、翻译数据库或
Phase 9C 以外的功能。Phase 9C2 冻结范围包括 per-turn locale switching、
deterministic snapshot/final novel export、terminal completion metadata、novel
status classification 和 export CLI；不引入 provider、Story SQLite 或通用框架。
合同同时固定历史 snapshot 的自有导出边界、冻结
Session 的单 Event 基线和稳定 Campaign snapshot 捕获协议。当前实现覆盖
Campaign-bound Story persistence、deterministic Narration Request、pending/resume、
structured claims、committed turn artifacts、status、verify、local CLI、locale
switching 和 deterministic novel export；Phase 9C1 与 Phase 9C2 均已冻结。

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
PC1 initial implementation candidate commit：`0510c4dc8d83f1e80f725bde693232662deba1f2`；
PC1 complete product-proof test correction：`7e8f16c7bf3908abb5424cab9457986f6e162674`；
PC1 comprehensive recovery/boundary correction：`0510c4dc8d83f1e80f725bde693232662deba1f2`；
PC1 final process/file boundary hardening：`3456178fb42eb6ae8c3debe33653924315e349d0`；
PC1 final acceptance correction：`96ffe3eefa9ea6558e3f9105f0a5a47838e3a1ce`。
以上 accepted implementation 已冻结为 `pc1-frozen`；冻结范围为
`src/tgn/play/**` 与 `tests/play/**`。冻结生产实现和测试不得原地编辑；未来缺陷
必须经过显式 PC1 reopen，或由新的 superseding milestone/phase 以新的 implementation
SHA 和新的 freeze tag 处理。PC1 freeze tag 不得移动、删除或重建。
PC1 使用 `src/tgn/play/**` 提供 `new`、`resume`、`narrate`、`status`、`verify` 和
`export`，只组合冻结 Campaign/Story 的公开 service API；不创建 Client 数据库、provider
adapter 或 Phase 9D/10 功能。PC1 本轮回归结果为 `tests/play 101 passed`、affected 集
`518 passed, 2 skipped`、全仓 `1740 passed, 2 skipped`；`src/tgn/play 97.11%`、
`src/tgn/story 96.95%`、`src/tgn/campaign 97.55%`、`src/tgn/projection 100%`、
full `src/tgn 97.05%`；warning-as-error 为 `0 warnings`。POSIX 使用
`start_new_session=True` 与 process-group cleanup，Windows 使用 operation-owned Job
Object 的 `KILL_ON_JOB_CLOSE`；response file 在 `O_NONBLOCK`、祖先 component、handle/path
identity 和最终 observable 复核下读取，CLI JSON 对 terminal controls 使用合法 JSON
escape。真实 WSL/POSIX `tests/play` 为 `101 passed`。唯一 skips 是 Windows 上既有的两个
POSIX FIFO 测试。

PC1 freeze verification record：`tests/play` `101 passed`；affected
`tests/play tests/campaign tests/story` `518 passed, 2 skipped`；full suite
`1740 passed, 2 skipped`；full serial `1740 passed, 2 skipped`；real WSL/POSIX
`tests/play` `101 passed`。Coverage 为 `src/tgn/play 97.11%`、
`src/tgn/story 96.95%`、`src/tgn/campaign 97.55%`、`src/tgn/projection 100.00%`、
full `src/tgn 97.05%`；warnings `0`。唯一 skips 为
`tests/campaign/test_no_follow.py::test_campaign_fifo_is_rejected_on_posix` 与
`tests/campaign/test_no_follow.py::test_copy_fifo_source_is_rejected_on_posix`，原因是
最终 Windows full-suite 主机无法创建 POSIX FIFO；PC1 自身没有新增 skip。

PC1 冻结不改变架构边界：PC1 是 thin outer client，Campaign/Engine 仍是 authority，
Story 仍是 derived/non-authoritative artifact；external narrator 是 trusted local
adapter；process containment 只是 operational cleanup，不是 security sandbox。不存在
Client database 或 provider framework。

下一里程碑方向为：

**Phase 10 — Capability Foundation and Stackable Protagonist Gift**

Phase 10 将建立一个 holder 持有多个、带 provenance 的 Capability，并让这些
Capability 进入确定性 action 或明确的局部 rule path。第一条实现路线是可持续产生
后续固定 Capability 的 protagonist core gift。Phase 10A 现在锁定为
Genesis Core Gift + First Deterministic Use Loop：player 持有 genesis 的
devour_evolution，通过明确的 DEVOUR_REMAINS action 消耗一个 eligible defeated
remains，并确定性获得 1 essence。Phase 10A implementation candidate 位于
`89e32661b2d26e58c21d09691df4bbc40ff0a2d1`，尚未冻结。Phase 9D 仍 deferred，且
不是 Phase 10 前置条件。

Phase 10A gameplay contract 已锁定；本轮只补充其
phase10a-devour-overlay-v1 bundle 与 Projection bridge 设计。完整 Campaign 路径
必须经过可重验证的 World bundle、Projection bundle、Campaign、Story 和冻结的
PC1 generic choice renderer；不增加 initial-state override seam。mvp-rewrite
现在包含 Phase 10A candidate code/tests 与 documentation；没有 Phase 10 freeze tag。

Phase 10A candidate verification：`tests/phase10` `62 passed`；full suite
`1802 passed, 2 skipped`；warning-as-error `0 warnings`；full `src/tgn` coverage
`97.01%`，`src/tgn/projection` `100.00%`，`src/tgn/gameplay` `98.33%`，
`src/tgn/worldgen` `96.60%`。唯一 skips 仍是 Windows 主机无法创建 POSIX FIFO 的两个既有
Campaign 测试；Phase 10A 没有新增 skip。

Phase 10 不得提前建立 EffectSystem、AbilityGraph、SkillTree mega-framework、generic
rule DSL、plugin/handler registry，或在 Core 中加入 world-specific branching。
现有 pending Narration Request 的自身 locale 是恢复时的权威值；只有新建 request
使用一次性 locale override，下一次新 request 回到 Story initial locale。Campaign
manifest 与 Session 的 campaign/session ID、actor ID、max_decisions 在 Story 初始化前
通过公开 model 做同 Campaign 绑定校验；外部 NarrationResponse 的字段、hash、locale、
claims 或 prose 错误统一返回 `PLAY_NARRATOR_FAILED`，并保留 exact pending request。
Windows 手工命令明确标为 `PowerShell command`，使用单引号参数；它不是安全沙箱。
外部 narrator executable 是用户选择的 trusted local adapter；PC1 不隔离文件系统、网络、
凭据或 hostile native code。POSIX process group 与 Windows Job Object 只提供 bounded
operational cleanup，不是 security isolation boundary；Windows `Popen →
AssignProcessToJobObject` 之前的恶意逃逸不在保证范围内。reader 线程必须在成功返回前
结束。
Phase 9C2 conditional-replacement correction：`b5fa586fb7e0838a95e14fb445508f4b5d8a32e6`。`novel.md` 的已有目标现在
必须以完整 expected observable 进行条件替换；POSIX 使用 anchored exchange 保留
displaced target，Windows 使用 `ReplaceFileW` 及 writer-owned backup；parent、target
和 writer artifact 在原子操作后再次校验，竞争者不会被覆盖或删除。CLI 的
`ReplaceFileW` 失败会保留精确的 `1175`、`1176` 和 `1177` outcome，并在 bound
Story parent 内重新检查 target、replacement、backup 与 retained writer HANDLE。
可证明的 `1177` partial layout 会先以 no-replace 恢复 expected target；未知对象
只会触发 bounded failure，不会被删除。POSIX displaced expected target 也只在
完整 observable 相等时清理，recoverable failure 不留下 `.tmp` 或 `.backup`。
`--accepted-decisions` 只接受 canonical non-negative integer。Phase 9C2 冻结前最终验证：
Story `244 passed`、Story coverage `96.95%`；Campaign `173 passed, 2 skipped`、
Campaign coverage `97.55%`；Worldgen `150 passed`；Projection `112 passed`、Projection
coverage `100%`；Session `74 passed`；LLM Player `63 passed`；Phase 8 autoplay
`1 passed`；全仓 `1639 passed, 2 skipped`、全仓 coverage `97.04%`；warning-as-error
全仓回归为 `0 warnings`。冻结门禁耗时为：focused parallel `118 passed` / `6.73s`；
Story parallel `244 passed` / `10.09s`；full parallel coverage `1639 passed, 2 skipped` /
`14.55s`；critical serial `118 passed` / `9.81s`；full serial `1639 passed, 2 skipped` /
`63.05s`。使用 pytest-xdist `3.8.0`，12/12 worker、WorkStealing，
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
process. Phase 9C1 is frozen at `phase-9c1-frozen`; Phase 9C2 is frozen at
`phase-9c2-frozen` and is immutable.

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
`phase-9c1-frozen`; Phase 9C2 is frozen at `phase-9c2-frozen` and is immutable.

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
