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
Phase 8 is an implementation candidate for a provider-neutral minimal LLM
Player adapter and RecordedDecision Replay. Neither phase implements a general
relationship system or any of the deferred relationship features below.

The fact that a local slice exists does not mean that its generalized framework,
multi-actor version, or alternate WorldPack variants are implemented.

PC1 is frozen at `pc1-frozen`. Phase 10 is a documentation candidate only:
Capability Foundation and Stackable Protagonist Gift. Phase 10 implementation has
not started and Phase 10 is not frozen.

The Phase 10A Feature Contract is locked as an implementation candidate, not as
production code. It fixes one genesis `devour_evolution` CapabilityGrant for the
`player` holder, one `DEVOUR_REMAINS` action, one `DEVOUR_RESOLVED` Event, and one
deterministic essence accumulation slice. Phase 10A production implementation has
not started and Phase 10 remains unfrozen.

### Active design direction, not implementation

The Phase 10 foundation direction is limited to:

- stable Capability grant identity;
- a holder;
- source provenance and authoritative acquisition;
- multiple permanent grants coexisting;
- one bounded active action, one bounded passive/local rule path, and one bounded
  acquisition path.

The Phase 10A contract is the first deterministic-use loop only. A second
Capability and its acquisition provenance remain Phase 10B; a passive Capability
path remains Phase 10C. Capability authoring inside WorldGen remains deferred and
is not an implicit Phase 10A change to the existing WorldPack compiler. The fixed
`phase10a-devour-overlay-v1` bundle and its Projection bridge are product-fixture
contracts, not a generic overlay framework or arbitrary initial-state patch
system. Arbitrary Capability WorldGen authoring remains deferred.
Generic overlay frameworks and arbitrary initial-state patch systems remain
prohibited.

The Phase 10A Story public-facts bridge is now an explicit implementation
candidate, not a change to the frozen Phase 9C2 contract. Phase 9C2 v1 already
contains the bounded `public_event_facts[].facts` JSON object; the missing slice
is a narrow Story reconstruction adapter for `DEVOUR_RESOLVED`. It may derive
only `capability_id`, `essence_before`, `essence_gained`, `essence_after`, and
`remains_consumed` from the authoritative Event plus replayed before/after state.
The Narrator remains non-authoritative, legacy Event facts remain `{}`, and no
generic public-fact ontology or new Story format is introduced. The bridge has
not been implemented. Phase 10A acceptance remains blocked by the separately
tracked presenter `enemy_id` boundary and the `devour_overlay.py` coverage gap
(95.24%, missing lines 105/109/111).

Capability, CapabilityGrant, and source-system language describe the design boundary;
they do not authorize Python classes, database schema, Event additions, tests, or a
generalized registry in the current phase.

### Still deferred beyond the Phase 10 foundation

- Reward / Fortune / Lottery / Chest / Shop;
- Equipment / Artifacts / Spatial Storage;
- Companion / Pet / Summoning lifecycle;
- Fusion and joint-growth systems;
- Organization / Settlement;
- Counterfactual Simulation;
- Timeline Branching / Rewind;
- Domains / Conditional Rule Overrides.

Deferred modules may later grant or consume Capability facts, but Phase 10 must not
prebuild their internal architecture. The generalized Capability registry remains
deferred; plugin frameworks and future-proof interfaces remain prohibited.

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

### Phase 8 active candidate

- provider-neutral minimal LLM Player adapter;
- strict selection from engine-provided legal choices;
- immutable RecordedDecision export/import and zero-network replay.

The Phase 8 candidate does not include a real provider, network client, API
credential handling, model routing, or broader generative behavior.

### Still deferred after the Phase 8 local slice

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
