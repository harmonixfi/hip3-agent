# V3-055 — Alert engine + routing policy

## Status: todo

## Goal
Deliver high-signal alerts with clear actions and minimal spam.

## Deliverables
- Alert severity model: INFO/WARN/CRITICAL/EMERGENCY
- Templates with required fields (what happened, numbers, action, costs)
- Routing rules:
  - CRITICAL/EMERGENCY → DM (optional) + channel fallback
  - anti-spam cooldown per position
  - quiet hours support
- Output channel: Discord #funding-arbit (and/or DM)

## Acceptance / How to verify
- Simulated alerts don’t spam more than configured cooldown
- CRITICAL/EMERGENCY messages include action + cost estimate

## Docs
- docs/POSITION_MANAGER.md

## Notes
- Alerts without an action are noise.
