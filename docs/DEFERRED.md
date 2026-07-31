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

## Important Notice

> **Deferred does not imply planned architecture.**  
> Do not create abstractions for deferred features until a feature enters an active implementation phase.

This means:
- No "future-proof" interfaces for combat, trading, etc.
- No generic "entity component" systems
- No placeholder interfaces for peer agents or LLMs
- Keep the core minimal and focused

Features should only be added when there is concrete design work and implementation planned.
