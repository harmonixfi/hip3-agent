## Project
Chúng ta đang build OpenClaw agent và toàn bộ tools cần thiết cho agent này.
Mục đích của agent là trade delta neutral - funding arbitrage strategy.


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

