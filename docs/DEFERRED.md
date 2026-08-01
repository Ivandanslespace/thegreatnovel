# Deferred Features - TheGreatNovel MVP

This document lists features that are not part of the current implementation
contract. A feature may become active only after a concrete product problem,
WorldPack pressure, and its own Feature Contract are established.

## Current implementation boundary

The repository already contains local slices for Phases 1–7, including combat,
expedition, extraction, progression, build choice, event sourcing, replay,
persistence, and scripted autoplay. Phase 7 is frozen at `phase-7-frozen`.

Phase 7.5 is an implementation candidate for one persistent Named Actor,
minimal relationship fact, one autonomous consequence, and a Knowledge Boundary.
It does not implement a general relationship system or any of the deferred
relationship features below.

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
- LLM Player integration and broader LLM-driven world generation;
- LLM NPC autonomy, free-form romance, agent planners, vector memory, and
  emotion inference;
- broader external narration integration beyond the existing narration
  infrastructure contract.

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
