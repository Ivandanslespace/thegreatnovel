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
- marriage, pregnancy, reproduction, children, jealousy, love triangles,
  multiple simultaneous partners, polyamory rules, multi-person cultivation,
  dating simulation, romance economy, and relationship graph structures.

Current status:

```text
design principles recorded
implementation deferred
not part of Phase 7.5
must not be added to the minimal Named Actor slice
```

Implementation requires all of the following prerequisites:

- Phase 7.5 Named Actor + Knowledge Boundary has been externally verified;
- Phase 8 LLM Player permission boundaries have been externally verified;
- at least one ordinary Capability vertical slice has been externally verified;
- a real WorldPack has a demonstrated need for relationship-produced joint growth
  or another persistent relationship consequence.

These are not permanent prohibitions. Each future feature requires its own
product reason, ethical boundary, Knowledge Boundary, authority model, and
Feature Contract. In particular, future designs must preserve Actor agency,
formation history, and long-term consequences rather than letting Narrator or
LLM text invent or erase relationship facts.

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
