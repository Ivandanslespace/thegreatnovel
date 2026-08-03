# Deferred Features - TheGreatNovel MVP

This document lists features that are not part of the current implementation
contract. A feature may become active only after a concrete product problem,
WorldPack pressure, and its own Feature Contract are established.

## Current implementation boundary

The repository already contains local slices for Phases 1–7, including combat,
expedition, extraction, progression, build choice, event sourcing, replay,
persistence, and scripted autoplay. Phase 7 is frozen at `phase-7-frozen`.

Phase 7.5 is frozen at `phase-7.5-frozen` with one persistent Named Actor,
minimal relationship fact, one autonomous consequence, and a Knowledge Boundary.
Phase 8 is frozen at `phase-8-frozen` as the provider-neutral minimal LLM Player
adapter and RecordedDecision Replay. It does not implement a general
relationship system or any of the deferred relationship features below. Any
future correction must use an explicit reopen or superseding phase; this file
does not reopen the frozen implementation.

The fact that a local slice exists does not mean that its generalized framework,
multi-actor version, or alternate WorldPack variants are implemented.

## Deferred features

### Generalized gameplay systems

- generalized combat, expedition, extraction, or progression frameworks beyond
  the existing local slices;
- generalized talent, capability, relationship, scheduler, or actor registries;
- larger-scale organizations, settlements, economies, or social simulation;
- multiple WorldPacks and structurally different world contracts.

### World and AI expansion

- Public World peer simulation beyond the existing local boundary;
- LLM NPC autonomy, free-form romance, agent planners, vector memory, and
  emotion inference;
- broader external narration integration beyond the existing narration
  infrastructure contract.

### Still deferred after the Phase 8 frozen slice

- real provider integrations and API credential handling;
- multi-model, persona, and scenario experiment matrices;
- retry, recovery, and prompt-optimization policies;
- free-form action interpretation and agent planning;
- LLM NPC and LLM World Generator systems;
- broader generative systems and model-driven world simulation.

### Relationship and joint growth

The following remain deferred and are not part of the Phase 7.5 Named Actor
slice:

- Complete Romantic Relationship / Mutual Bond System;
- Relationship-produced Joint Capability / Dual Cultivation;
- richer relationship and family structures;
- multi-character bonds and relationship conflicts;
- reproduction or lineage mechanics;
- WorldPack-specific romance, partnership, or joint-growth systems;
- generalized relationship graphs or social simulation.

Current status:

```text
design principles recorded
implementation deferred
not part of Phase 7.5
must not be added to the minimal Named Actor slice
```

Under the current roadmap, the following are useful readiness signals rather than
permanent mandatory prerequisites:

- Phase 7.5 Named Actor and Knowledge Boundary experience;
- LLM Player permission-boundary experience where an LLM Player is involved;
- ordinary Capability experience where a Joint Capability is involved;
- a concrete WorldPack need;
- an independently reviewed Feature Contract.

A future external review may reorder these optional steps when a concrete
WorldPack creates an earlier, bounded, and testable product need. For example, a
pure scripted WorldPack may need to test relationship formation history before an
LLM Player exists; the absence of Phase 8 must not permanently prohibit that
bounded work.

The non-optional quality gates for any future relationship feature are:

- a concrete product need;
- a bounded Feature Contract;
- an explicit authority boundary;
- a Knowledge Boundary where relevant;
- deterministic verification;
- external review.

These categories are deferred, not prohibited. Their exact forms must be defined
only when a real WorldPack requires them. Each future feature must preserve Actor
agency, formation history, and long-term consequences rather than letting
Narrator or LLM text invent or erase relationship facts. Action executability is
not the same as willingness or consent, and the Engine does not make moral
choices for the player.

## Important notice

> **Deferred does not imply planned architecture.**

Do not create abstractions for deferred features until a feature enters an active
implementation phase. This means:

- no future-proof interfaces for deferred combat, trading, or relationships;
- no generic Entity Graph, Relationship Graph, Knowledge Graph, scheduler, or
  plugin framework;
- no placeholder interfaces for peer agents or LLMs;
- keep Core minimal and focused on the current causal slice.

Features should only be added when concrete design work and implementation are
planned together.

## Genesis Foundation / Phase 10 deferred boundaries

Phase 10G0 defines the Genesis architecture contract in documentation only. The
following items are intentionally deferred from Phase 10A. Each requires a
superseding contract, real implementation evidence, and independent review;
none may be smuggled into Phase 10A as a generic framework.

| Deferred item | Why it is not Phase 10A | Required contract and evidence before implementation |
|---|---|---|
| World Blueprint implementation | 10A only evaluates structured Requirement Proposals; it must not create a world design or Campaign. | Phase 10B Blueprint/World Bible schema, stable IDs, public/hidden boundary, reference validation, and fixture proof. |
| World Compiler v2 | 10A has no WorldPack compiler and must not change the frozen `phase9b-bounded-world-v1` meaning. | Phase 10C compiler identity, versioned schema, binding matrix, canonical artifact, hash, old-bundle verification and atomic publication proof. |
| Runtime profile boundary implementation | A second runtime profile is not needed to define the 10A report, and profile dispatch would broaden scope. | A real second structurally different profile plus a versioned adapter boundary, shared replay proof, and no theme-keyword branching. |
| Feature-local reducer migration | Moving frozen reducer logic would modify Phase 1–7 accepted behavior. | A superseding runtime phase with event ownership, reducer invariants, migration/replay proof, and explicit reopen or new boundary. |
| Feature-local invariant migration | Core invariants currently protect the frozen first slice; this is an architecture refactor, not request evaluation. | Feature Contract with state, legality, invariants, failure codes, old regression coverage and independent review. |
| Presentation v2 | 10A has no new runtime Action or player-visible schema. | New action contract, public/private projection rules, schema version, artifact hash and end-to-end presentation proof. |
| Story Context v2 | Narration is downstream of committed facts and cannot be used to fill missing Genesis semantics. | Versioned Story Context/claim contract, public knowledge boundary, deterministic reconstruction and prose non-authority proof. |
| PC2 | PC1 is frozen and 10A must have no Campaign/Session/Story side effects. | New PC2 milestone, implementation SHA, explicit file boundary, resume/replay proof and a new freeze tag. |
| Natural-language action semantics | 10A accepts structured proposals only; natural-language action interpretation is a separate ambiguity and legality problem. | Phase 12 contract for intent proposal, clarification, legality binding, rejection and replay. |
| Capability Foundation | A universal capability system would be a mega-framework before a real second need. | Phase 13 one or more concrete capability slices that share causal structure, each with State/Event/Reducer/Projection/Replay. |
| Cybernetic Intrusion | The current engine has no prosthesis entity, network state, scan, intrusion, defense or trace semantics. | A bounded Feature Contract and end-to-end vertical slice; narration alone is insufficient. |
| Habitat / Xuanwu | A label or progression cost helper does not prove Habitat ownership, upgrade, projection or runtime semantics. | Habitat entity/ownership/progression/resource contracts and a runnable WorldPack proof. |
| Peer Population | A public-world label is not autonomous peers, off-screen action, ranking or competition. | Peer state, goals, autonomous progression, public/private knowledge, Event and replay proof. |
| Mass Drop | “全民投放” is a social/runtime requirement, not a theme label. | Bounded population model, public event/competition semantics, cost budget and degraded-mode acknowledgement. |
| Runtime lazy expansion | Unseen content is not allowed to be rewritten silently; expansion is not a 10A report concern. | Phase 10C/11 child-seed namespace, parent hash, stable IDs, validation, sealing and replay proof. |
| Real LLM provider | 10A must be pure Python and network-free. | Provider boundary, credentials/security policy, deterministic artifact capture, failure isolation and explicit product approval. |
| Automatic repair | Unlimited repair can create hidden authority loops and unbounded latency. | Bounded error codes, finite retry budget, no Campaign side effects, timeout/failure proof. |
| Deep model matrix | 10A evaluates a proposal under one versioned catalog; it is not a provider benchmark. | Phase 10D/CI policy, reproducible fixtures, budget, model/version metadata and independent comparison. |

The old `devour_evolution` candidate remains historical only. The locally verified
ref `archive/phase10a-devour-candidate-2026-08-02` points to
`870284cc653e400603747dd9e14e41fa6df7795a`; it has no accepted freeze tag on this
branch and must not be restored as the default Genesis capability.
