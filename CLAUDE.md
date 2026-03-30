## Project
Chúng ta đang build OpenClaw agent và toàn bộ tools cần thiết cho agent này.
Mục đích của agent là trade delta neutral - funding arbitrage strategy.

## Development Standard:
### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately – don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes – don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests – then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.


## Docs:
Toàn bộ tài liệu, spec, plan sẽ nằm ở:
- `docs`
- `spec`


## Run project locally
- Env vars tại file `.arbit_env`. Hãy run `source .arbit_env` trước khi run các python command.


## Position Management Workflow

Playbook chi tiết: `docs/playbook-position-management.md`

Quick reference:
1. **Mọi thay đổi position bắt đầu từ** `config/positions.json` (source of truth)
2. **Sync xuống DB** bằng: `source .arbit_env && .venv/bin/python scripts/pm.py sync-registry`
3. **Verify**: `.venv/bin/python scripts/pm.py list`

Common operations:
- **Add position**: thêm object vào positions.json → sync-registry
- **Update qty (rebalance)**: sửa qty ở CẢ HAI legs (spot + perp) → sync-registry
- **Close position**: set `"status": "CLOSED"` → sync-registry
- **Pause position**: set `"status": "PAUSED"` → sync-registry

Multi-wallet: legs dùng `wallet_label` ("main" hoặc "alt"), resolved qua env var `HYPERLIQUID_ACCOUNTS_JSON`.


## Trading Decision Workflow

Mỗi khi analyze portfolio và đưa ra quyết định trading, PHẢI thực hiện 3 bước sau:

### 1. Trading Journal (bắt buộc sau mỗi session)
- Tạo file `tracking/journal/YYYY-MM-DD.md`
- Format: Context → Market Observations → Portfolio Analysis → Decisions (với rationale) → Action Items
- Mỗi decision phải có: rationale, timing, expected outcome
- Nếu cùng ngày có nhiều session, append hoặc tạo `-v2` suffix

### 2. Review Schedule (bắt buộc khi có position changes)
- Update `tracking/REVIEW_SCHEDULE.md`
- Mỗi position OPEN phải có: next review date, action criteria (positive/negative), notes
- Khi tới review date: pull fresh data → evaluate theo checklist → quyết định → journal → update schedule
- Completed reviews move xuống bảng "Completed Reviews" để giữ audit trail

### 3. Decision → Execute Flow
```
Analyze data → Quyết định (HOLD/EXIT/ENTER/REBALANCE)
  → Ghi journal entry
  → Update review schedule
  → Execute: edit positions.json → pm.py sync-registry → verify
  → Confirm action items với timeline
```

### Review Cadence
- **Daily**: Morning report (09:00 ICT) — scan funding trends, flag anomalies
- **Per-position**: Review theo schedule trong REVIEW_SCHEDULE.md
- **Ad-hoc**: Khi có funding shock (>30% APR swing trong 24h) hoặc market event

