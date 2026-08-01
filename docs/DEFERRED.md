# Deferred Features - TheGreatNovel MVP

This document lists features that are **explicitly not implemented** in the current MVP, but may be considered for future phases.

## Current Phase Scope

The current MVP focuses on:
- Deterministic game state management
- Event sourcing and replay
- Basic action validation and resolution
- Scripted agent testing infrastructure

## Deferred Features

The following features are deferred and will **not** be implemented until they enter an active development phase:

### Core Gameplay Systems
- Combat mechanics
- Expedition systems
- Extraction mechanics
- Character progression systems
- Talent choice systems

### World Features
- Public world simulation
- Peer agents (other players)
- Trading economy
- Ranking and leaderboard systems
- Multiple world packs

### AI Integration
- Narrator LLM integration
- LLM player agent
- LLM world generator

### Migration
- Legacy save migration tools

### Future Relationship and Joint Growth

The following remain deferred and are not part of the Phase 7.5 Named Actor
slice:

- Complete Romantic Relationship / Mutual Bond System
- Relationship-produced Joint Capability / Dual Cultivation

Current status:

```text
design principles recorded
implementation deferred
not part of Phase 7.5
must not be added to the minimal Named Actor slice
```

Before implementation, all of the following must be true:

- Phase 7.5 Named Actor + Knowledge Boundary has been externally verified;
- Phase 8 LLM Player permission boundaries have been externally verified;
- at least one ordinary Capability vertical slice has been externally verified;
- a real WorldPack has a demonstrated product need for couple-based joint growth.

The following are also deferred:

- marriage
- pregnancy
- reproduction
- children
- jealousy
- love triangles
- multiple simultaneous partners
- polyamory rules
- multi-person cultivation
- dating simulation
- romance economy
- relationship graph

These are not permanent prohibitions. Each future addition requires its own
product reason, ethical boundary, and Feature Contract. The current MVP does
not implement them and must not create preparatory framework code for them.

## Important Notice

> **Deferred does not imply planned architecture.**  
> Do not create abstractions for deferred features until a feature enters an active implementation phase.

This means:
- No "future-proof" interfaces for combat, trading, etc.
- No generic "entity component" systems
- No placeholder interfaces for peer agents or LLMs
- Keep the core minimal and focused

Features should only be added when there is concrete design work and implementation planned.
