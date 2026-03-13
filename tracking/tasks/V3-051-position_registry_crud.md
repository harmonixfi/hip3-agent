# V3-051 — Position Registry + CRUD

## Status: todo

## Goal
Create a single source of truth for what positions are “managed” and how legs map across venues.

## Deliverables
- Position registry format (YAML/JSON) under `config/positions.json` (or `config/positions.yaml`)
- Loader + validator module (e.g. `tracking/position_manager/registry.py`)
- CRUD helpers:
  - add / update / pause / close position
  - attach legs
- Write-through into DB tables (`pm_positions`, `pm_legs`)

## Acceptance / How to verify
- `pm list` prints positions from registry/DB
- Can create a dummy position with 2 legs and see it in DB
- Validation catches missing venue/inst_id or invalid sides

## Docs
- docs/POSITION_MANAGER.md

## Notes
- Registry should support multi-leg strategies: SPOT_PERP and PERP_PERP.
