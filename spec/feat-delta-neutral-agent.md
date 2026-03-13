---
tags:
  - harmonix
  - feature
  - trading
  - agent
type: spec
status: draft
created: 2026-03-05
updated: 2026-03-11
owner: Bean
---

# Feature: Delta Neutral Funding Rate Agent

## Objective

Build OpenClaw agent **advisory** giúp Bean vận hành strategy delta-neutral funding rate trên Hyperliquid — theo dõi positions, phát hiện cặp nên đảo/exit, và recommend candidate pairs mới.

> [!info] Advisory Only
> Agent KHÔNG tự execute lệnh. Chỉ phân tích + gợi ý. Bean quyết định cuối cùng.

---

## Scope

### Phase 1 — Research: Strategy Rules

> [!warning] Prerequisite
> Phase 1 phải hoàn thành trước khi build agent logic ở Phase 2.

- Research + define **criteria chọn cặp** để mở position
- Define **trigger để unwind** và rotate sang position mới
- Define cách **điều chỉnh tỉ trọng** giữa các pairs
- Validate rules bằng historical data trên Hyperliquid

Output: `06-research/res-delta-neutral-rules.md` — strategy rules document đã review + approve bởi Bean.

### Phase 2 — Build: Data Pipeline & Agent

- **Data pipeline**: job fetch funding rate data từ Hyperliquid (scheduled, < 1h delay)
- **Portfolio tracking**: positions với các chỉ số — start date, symbol, total earned funding, trading fees, net profit, APR
- **Daily report** gửi qua chat (Telegram/Discord/WhatsApp) theo lịch cố định
- **Stability scoring** top 20 pairs: `0.55×APR14 + 0.30×APR7 + 0.15×APR_latest`
- **Position advisory** per position: HOLD / MONITOR / EXIT / INCREASE SIZE kèm lý do

### Out of Scope

- Auto-execution (agent không tự mở/đóng lệnh)
- Multi-exchange (chỉ Hyperliquid)
- Backtesting engine

---

## Outputs

| # | Deliverable | Phase |
|---|-------------|-------|
| 1 | Strategy rules document (`res-delta-neutral-rules.md`) | Phase 1 |
| 2 | Funding rate data pipeline (cron job, Hyperliquid) | Phase 2 |
| 3 | Daily portfolio report qua chat | Phase 2 |
| 4 | Top 20 candidate pairs ranking (stability score) | Phase 2 |
| 5 | Position health advisory (HOLD/MONITOR/EXIT per position) | Phase 2 |

---

## Report Format (Daily)

### Portfolio Summary

Mỗi dòng là 1 position đang mở:

| Symbol | Amount ($) | Start Time | Avg 15d Funding ($) | Funding 1d / 2d / 3d ($) | Open Fees ($) | Breakeven Time | Advisory |
|--------|-----------|------------|---------------------|--------------------------|---------------|----------------|----------|
| BTC    | $x,xxx    | YYYY-MM-DD | $xx.xx              | $x.xx / $x.xx / $x.xx   | $x.xx         | X days         | HOLD     |
| ETH    | $x,xxx    | YYYY-MM-DD | $xx.xx              | $x.xx / $x.xx / $x.xx   | $x.xx         | X days         | MONITOR  |

**Field definitions:**
- `Amount` — notional size của position (USD)
- `Avg 15d Funding` — trung bình funding earned mỗi ngày trong 15 ngày gần nhất
- `Funding 1d / 2d / 3d` — funding earned trong 1, 2, 3 ngày gần nhất (để detect trend)
- `Open Fees` — phí trading lúc mở position (taker fee cả 2 legs)
- `Breakeven Time` — thời gian để funding earned bù đủ open fees (= Open Fees ÷ Avg Daily Funding)

**Advisory labels:**
- `HOLD` — position đang tốt, tiếp tục giữ
- `MONITOR` — cần theo dõi, cân nhắc exit nếu metrics tiếp tục xấu
- `EXIT` — nên đóng position
- `INCREASE SIZE` — funding ổn định, có thể tăng size

### Top 10 Rotation Candidates - General

Top 10 symbols **không đang hold** và **không thuộc Felix equities** xếp theo stability score.

| Rank | Symbol | Venue | APR14 | APR7 | APR 1d / 2d / 3d | Stability Score | Note |
|------|--------|-------|-------|------|-------------------|-----------------|------|
| 1    | xxx    | venue | x%    | x%   | x% / x% / x%     | x.xx            |      |

> [!tip] Stability Score Formula
> `Score = 0.55 × APR14 + 0.30 × APR7 + 0.15 × APR_latest`
> Ưu tiên pairs có funding rate **ổn định theo thời gian**, không chỉ cao nhất tại thời điểm hiện tại.

### Top 10 Rotation Candidates - Equities

Top 10 symbols **không đang hold** và **thuộc Felix equities** xếp theo cùng stability score.

| Rank | Symbol | Venue | APR14 | APR7 | APR 1d / 2d / 3d | Stability Score | Note |
|------|--------|-------|-------|------|-------------------|-----------------|------|
| 1    | xxx    | venue | x%    | x%   | x% / x% / x%     | x.xx            |      |

Mỗi rotation section phải có thêm `Flagged Candidates` ở cuối để show các name bị loại vì stale / low sample / broken persistence / severe flags, thay vì silently skip. Nếu Felix cache chỉ bị stale thì vẫn được split/rank, nhưng section phải ghi warning degraded rõ ràng.

### Rotation Cost Analysis

Khi Bean muốn đảo từ position hiện tại sang 1 candidate pair, agent cần show rõ:

| | |
|--|--|
| **Close position** | Symbol đang hold |
| Close fees ($) | Taker fee để đóng 2 legs |
| **Open new position** | Symbol muốn rotate vào |
| Open fees ($) | Taker fee để mở 2 legs |
| **Total switch cost ($)** | Close fees + Open fees |
| Expected daily funding ($) | Avg 15d funding của pair mới (tính cho cùng notional) |
| **Breakeven time** | Total switch cost ÷ Expected daily funding |

> [!info] Ví dụ
> Đóng BTC ($2 close fee) → Mở DOGE ($1.5 open fee) = $3.5 tổng cost.
> Nếu DOGE expected daily funding = $5/ngày → breakeven sau **~17 giờ**.

`Rotation Cost Analysis` là on-demand block, không phải phần bắt buộc của daily report.

---

## DoD (Acceptance Criteria)

### Phase 1

- [ ] Strategy rules document hoàn chỉnh: criteria chọn cặp, trigger unwind, logic tỉ trọng
- [ ] Rules đã review + approve bởi Bean

### Phase 2

- [ ] Funding rate data cập nhật với delay < 1 giờ
- [ ] Daily report gửi đúng giờ qua chat, assemble từ 3 section: `Portfolio Summary`, `Top 10 Rotation Candidates - General`, `Top 10 Rotation Candidates - Equities`
- [ ] Mỗi position có advisory label (HOLD/MONITOR/EXIT/INCREASE SIZE) kèm lý do ngắn
- [ ] Hai rotation sections không trùng ranked symbols; `general` loại Felix equities, `equities` chỉ giữ Felix equities
- [ ] Rotation sections hiển thị `Flagged Candidates` cho weak/stale setups
- [ ] Rotation cost analysis: khi chỉ định cặp muốn đảo, agent tính được close fees + open fees + breakeven time
- [ ] Agent chạy stable ≥ 3 ngày liên tục không miss report

---

## Open Questions

- [ ] Funding rate fetch frequency bao nhiêu là đủ? (1h, 4h, 8h?)
- [ ] Threshold APR tối thiểu để một pair qualify vào top 20?
- [ ] Report gửi lúc mấy giờ mỗi ngày?
- [ ] Cần track PnL unrealized (mark-to-market) hay chỉ realized funding?
