# Runbook: Loris Funding Data Sync & Audit

## Overview

`data/loris_funding_history.csv` là nguồn dữ liệu funding rate cho toàn bộ candidate scoring và carry computation. File này được build bởi:
- **Live collector** (`pull_loris_funding.py`): cron chạy mỗi giờ trên trading-sandbox, append 1 row/symbol/venue
- **Backfill script** (`pull_loris_backfill_history.py`): pull historical data từ Loris API, chạy thủ công khi cần

Stale threshold: **12h** (hardcoded trong `report_daily_funding_with_portfolio.py`).

---

## 1. Sync file về local

```bash
rsync -avz --progress \
  trading-sandbox:/home/ubuntu/hip3-agent/data/loris_funding_history.csv \
  data/loris_funding_history.csv
```

Verify sau rsync:
```bash
tail -3 data/loris_funding_history.csv
wc -l data/loris_funding_history.csv
```

Expected: last timestamp trong vòng 1-2h so với hiện tại.

---

## 2. Audit data quality

```bash
source .arbit_env
.venv/bin/python scripts/audit_loris_data.py
```

Output: `docs/reports/loris_data_quality.md`

### Đọc kết quả audit

**Venue Summary** — check date range và stale count. Nếu tất cả symbol của 1 venue đều stale cùng 1 ngày → cron trên server đã dừng.

**Stale symbols** — phân loại:
| Pattern | Nguyên nhân | Action |
|---|---|---|
| Tất cả symbol, stale cùng 1 ngày | Cron stopped | Restart cron (xem mục 4) |
| 1 symbol, stale lâu (>7 ngày) | Symbol delisted khỏi Loris | Ignore, mark DEAD |
| Vài symbol, stale gần đây | Loris tạm ngưng tracking | Thử backfill |

**Felix Equity Coverage** — chỉ 26/205 symbols có data là bình thường. Loris không track stock equities theo tên ticker; 179 symbols còn lại không có funding data trên bất kỳ venue nào.

**Legacy HL symbols** (AAPL, TSLA, NVDA, v.v. trên `hyperliquid`, stale từ 2026-01-14) — đây là data bị label sai venue từ trước. Script audit đã tự động exclude. Ignore.

**Gap events** — hầu hết gap bắt nguồn từ 2 outage đã biết:
- 2026-03-12 → 2026-03-18 (5.5 ngày, toàn bộ venue)
- 2026-04-01 → 2026-04-09 (8 ngày, phần lớn venue)

Gap trong lịch sử không ảnh hưởng đến current scoring nếu data hiện tại fresh.

---

## 3. Backfill khi thiếu data

### Khi nào cần backfill

- Cron mới restart sau downtime → cần fill gap
- Symbol cụ thể có ít sample trong 14 ngày (LOW_14D_SAMPLE flag)
- Mới add symbol mới vào `config/positions.json` → cần history để tính APR14

### Commands

**Backfill toàn bộ 30 ngày gần nhất** (dùng sau khi cron restart):
```bash
ssh trading-sandbox
cd /home/ubuntu/hip3-agent && source .arbit_env
.venv/bin/python scripts/pull_loris_backfill_history.py --days 30
```

**Backfill từ ngày cụ thể** (fill 1 gap xác định):
```bash
.venv/bin/python scripts/pull_loris_backfill_history.py \
  --start 2026-04-10 --end 2026-04-20
```

**Backfill cho symbol cụ thể** (group theo start date sớm nhất của stale):
```bash
# Symbols stale từ tháng 1 (ví dụ: SPACEX, USA500, US500)
.venv/bin/python scripts/pull_loris_backfill_history.py \
  --symbols SPACEX,USA500,US500 --start 2026-01-19

# Symbols stale từ tháng 3
.venv/bin/python scripts/pull_loris_backfill_history.py \
  --symbols EWJ,META,AAPL,TSM,GOOGL --start 2026-03-19

# Symbols stale từ đầu tháng 4
.venv/bin/python scripts/pull_loris_backfill_history.py \
  --symbols SUPER,LINEA,AMZN,TNSR,MET,MU,SNDK,EWY,NATGAS \
  --start 2026-04-01
```

Backfill mất ~10-20 phút tùy số symbol (có sleep giữa request để tránh rate limit).

### Sau khi backfill xong

Rsync lại về local rồi chạy audit để verify:
```bash
rsync -avz --progress \
  trading-sandbox:/home/ubuntu/hip3-agent/data/loris_funding_history.csv \
  data/loris_funding_history.csv

.venv/bin/python scripts/audit_loris_data.py
```

### Khi backfill không add được rows mới

```
appended_rows=110 dupes_skipped=347
```

- `dupes_skipped` cao → data đã tồn tại, bình thường
- `appended_rows=0` cho 1 symbol cụ thể → Loris không có historical data (symbol bị delisted). Mark symbol đó là DEAD, không action thêm.

---

## 4. Kiểm tra và restart cron trên server

```bash
ssh trading-sandbox

# Check container còn chạy không
docker compose ps
docker compose logs --tail 50

# Check log của live collector
docker exec harmonix-api cat /app/logs/pull_loris_funding.log 2>/dev/null | tail -20

# Restart nếu cần
docker compose restart

# Verify cron đang chạy
docker exec harmonix-api crontab -l
```

Sau khi restart, backfill gap bị miss (xem mục 3).

---

## 5. Known dead symbols (không cần action)

Các symbol đã bị remove khỏi Loris feed, không thể backfill:

| Venue | Symbol | Last seen | Lý do |
|---|---|---|---|
| `kinetiq` | SPACEX | 2026-01-20 | Delisted khỏi Kinetiq |
| `kinetiq` | US500 | 2026-03-21 | Delisted khỏi Kinetiq |
| `felix` | USA500 | 2026-03-21 | Delisted khỏi Felix |
| `tradexyz` | EWJ, META, AAPL, TSM, GOOGL | 2026-03-26 ~ 04-01 | Stock perps removed |
| `tradexyz` | AMZN, MU, SNDK, EWY | 2026-04-10 ~ 04-13 | Stock perps removed |
| `hyperliquid` | (stock tickers) | 2026-01-14 | Legacy mislabeled data |
