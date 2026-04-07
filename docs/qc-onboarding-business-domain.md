# QC Onboarding — Business Domain & Metrics

> Tài liệu này giúp QC hiểu đúng các khái niệm và công thức để verify report, dashboard, và API của hệ thống OpenClaw.

---

## Phần 1: Strategy là gì

### Delta-Neutral Funding Arbitrage

Hệ thống đồng thời giữ **2 vị thế đối xứng** trên cùng 1 asset:

```
SPOT long BTC  +  PERP short BTC
```

**Tại sao "neutral"?**
Nếu giá BTC tăng → spot lãi, perp lỗ tương đương → tổng gần bằng 0.
Không có rủi ro về chiều giá (directional risk).

**Kiếm tiền từ đâu?**
Từ **funding rate** — khoản phí định kỳ trả giữa long và short trên thị trường perp.
Khi thị trường bullish, rate dương → short **nhận tiền** từ long.
Strategy của chúng ta: short perp → nhận funding đều đặn.

---

### Funding Rate là gì

- Cứ mỗi **8 tiếng**, sàn perp tái phân phối một khoản phí giữa phe long và phe short
- Rate **dương** → long trả cho short (short nhận tiền — đây là trường hợp phổ biến khi thị trường bullish)
- Rate **âm** → short trả cho long (short mất tiền — rủi ro, cần monitor)
- Đơn vị: **% per 8h**, ví dụ `0.01%` = 10 bps/8h ≈ **13.5% APR**

---

### Cấu trúc Position

Mỗi **position** gồm 2 **legs**:

| Leg | Side | Venue | Mục đích |
|---|---|---|---|
| Spot leg | LONG | Hyperliquid Spot, OKX... | Giữ tài sản thật |
| Perp leg | SHORT | Hyperliquid Perp, OKX... | Nhận funding |

Một position được coi là **delta-neutral** khi `size` của 2 legs bằng nhau.

---

## Phần 2: Equity (Vốn)

### Hyperliquid báo cáo equity như thế nào

Hyperliquid trả về 3 con số chính cho mỗi tài khoản:

| Field | Ý nghĩa |
|---|---|
| `accountValue` | **Tổng equity** = tiền mặt + unrealized PnL của toàn bộ positions |
| `totalMarginUsed` | Phần margin đang bị khóa bởi các positions đang mở |
| Available balance | `accountValue − totalMarginUsed` = tiền có thể rút/dùng |

> **Quan trọng:** `accountValue` **đã bao gồm unrealized PnL**. Khi giá thay đổi, số này thay đổi theo ngay cả khi chưa chốt lệnh.

### Multi-wallet (Main + Alt)

Hệ thống dùng **2 ví Hyperliquid** (wallet main và wallet alt).

```
Total Equity = accountValue(wallet_main) + accountValue(wallet_alt)
```

**Khi verify trên Hyperliquid UI:** phải cộng cả 2 ví mới ra đúng số trên dashboard.

---

## Phần 3: Các Metrics Chính

### 3.1 Unrealized PnL (uPnL)

**Định nghĩa:** Lãi hoặc lỗ của positions **đang mở, chưa chốt**. Thay đổi theo giá realtime.

**Công thức:**

```
LONG leg:  uPnL = (giá hiện tại − giá vào)  × số lượng
SHORT leg: uPnL = (giá vào − giá hiện tại)  × số lượng
```

**Ví dụ thực tế:**

```
Position BTC delta-neutral, size = 0.1 BTC:

  SPOT leg (LONG):  vào @ 80,000 | hiện tại 82,000
    uPnL = (82,000 − 80,000) × 0.1 = +$200

  PERP leg (SHORT): vào @ 80,100 | hiện tại 82,100
    uPnL = (80,100 − 82,100) × 0.1 = −$200

  Net uPnL = +$200 − $200 = ~$0   ← delta neutral hoạt động đúng
```

**Dấu hiệu bình thường:** uPnL của 2 legs gần bằng nhau và triệt tiêu nhau.

**Cờ đỏ:** Nếu net uPnL lệch lớn hơn 1% notional → có vấn đề về size mismatch hoặc giá bị stale.

---

### 3.2 Realized PnL

**Định nghĩa:** Lãi hoặc lỗ **đã về tài khoản**, không thay đổi theo giá nữa.

Gồm 3 thành phần:

| Loại | Dấu | Khi nào phát sinh |
|---|---|---|
| Funding earned | **+** | Mỗi 8 tiếng, khi rate dương và đang short perp |
| Trading fees | **−** | Mỗi khi vào/ra lệnh mua bán |
| Trade PnL | +/− | Khi close position ở giá khác giá entry (basis P&L) |

**Phân biệt uPnL vs Realized PnL:**

| | uPnL | Realized PnL |
|---|---|---|
| Đã về tài khoản? | Chưa | Rồi |
| Thay đổi theo giá? | Có | Không |
| Hiển thị khi? | Position còn OPEN | Cộng dồn mọi lúc |
| Khi close position | Biến mất | Được chốt vào realized |

---

### 3.3 Funding Earned vs Fees Paid

Đây là 2 con số **tách biệt** cần phân biệt rõ trên report.

**Funding Earned:**
- Là tiền nhận được từ phe long (qua sàn) mỗi 8 tiếng
- Luôn là **số dương** trong ledger
- Verify: vào Hyperliquid UI → tab **Funding History** → tổng phải khớp

**Fees Paid:**
- Là phí giao dịch trả cho sàn khi đặt lệnh mua/bán
- Luôn là **số âm** trong ledger
- Verify: vào Hyperliquid UI → tab **Trade History** → cột fee, tổng phải khớp

**Net Funding = Funding Earned − Fees Paid**

> Ví dụ: Nhận $500 funding, trả $80 phí → Net = $420 thực sự kiếm được.

---

### 3.4 APR (Annual Percentage Rate)

**Định nghĩa:** Tỷ lệ sinh lời hàng năm, quy đổi từ funding rate hiện tại.

**Công thức:**

```
APR = funding_rate_8h × 3 × 365 × 100%

Trong đó:
  funding_rate_8h  = rate của kỳ 8h hiện tại (dạng thập phân)
  × 3              = 3 kỳ 8h trong 1 ngày
  × 365            = số ngày trong năm
  × 100            = chuyển sang %
```

**Ví dụ:**
```
Funding rate = 0.05% per 8h
APR = 0.0005 × 3 × 365 × 100 = 54.75% APR
```

**Các loại APR trên dashboard:**

| Tên | Cách tính | Ý nghĩa |
|---|---|---|
| Current APR | Từ funding rate 8h gần nhất | Snapshot tại thời điểm xem |
| 7D APR | Trung bình funding 7 ngày qua | Xu hướng tuần |
| 14D APR | Trung bình có loại outlier, 14 ngày | Bền vững, tin cậy hơn |
| Realized APR | Cashflow thực tế ÷ vốn ÷ số ngày × 365 | **Con số thực đã nhận về** |

> **Realized APR là con số quan trọng nhất để QC verify** — đây là lợi nhuận thực tế, không phải ước tính.

---

### 3.5 Net Carry

**Định nghĩa:** Thu nhập ròng từ funding sau khi trừ fees, quy đổi về mức 8h.

```
Gross Carry (8h) = Funding nhận trong kỳ 8h / Notional
Net Carry (8h)   = Gross Carry − Fees trung bình (8h)

Gross APR = Gross Carry × 3 × 365 × 100%
Net APR   = Net Carry × 3 × 365 × 100%
```

**Tại sao cần phân biệt:**
- Report thường hiển thị **Gross APR** (chưa trừ fees)
- **Net APR** mới là số tiền thực chất kiếm được
- Fees thường chiếm 0.5–2% APR tùy tần suất rebalance

**Cờ đỏ:** Net Carry âm liên tục → funding rate đã đảo chiều, đang lỗ.

---

### 3.6 Entry Basis & Exit Basis (Basis Spread)

**Khái niệm:** Chênh lệch giá giữa spot và perp tại thời điểm vào/thoát lệnh.

**Entry Basis:**
```
Entry Basis = (giá vào spot / giá vào perp) − 1

Ví dụ:
  Mua spot BTC @ 80,000
  Short perp BTC @ 80,160
  Entry Basis = (80,000 / 80,160) − 1 = −0.20%  (−20 bps)
```

**Exit Basis:**
```
Exit Basis = (giá thoát spot / giá thoát perp) − 1
```

**Spread PnL:**
```
Spread PnL = (Exit Basis − Entry Basis) × 10,000  [đơn vị: bps]

Ví dụ:
  Entry Basis = −20 bps, Exit Basis = −5 bps
  Spread PnL = (−5) − (−20) = +15 bps  ← lãi thêm 15 bps từ basis
```

**Cách đọc:**
- Basis âm khi vào (spot rẻ hơn perp) → **tốt**, đang mua rẻ hơn
- Basis dương khi ra (spot đắt hơn perp) → **xấu**, đang thoát đắt hơn
- Basis tightening (basis thu hẹp từ âm về 0) → lãi basis

---

## Phần 4: Vòng Đời Position

```
OPEN → PAUSED → CLOSED
```

| Trạng thái | Funding | uPnL | Realized PnL |
|---|---|---|---|
| OPEN | Tích lũy mỗi 8h | Thay đổi theo giá | Cộng dồn |
| PAUSED | Ngừng thu thập | Vẫn fluctuate | Giữ nguyên |
| CLOSED | Không còn | = 0 | Finalized |

---

## Phần 5: Checklist Verify Theo Tình Huống

### Khi position mới mở

- [ ] Tồn tại đúng 2 legs: 1 LONG (spot) + 1 SHORT (perp)
- [ ] Size của 2 legs gần bằng nhau (delta neutral)
- [ ] Entry price hợp lý, khớp với giá thị trường lúc vào lệnh
- [ ] Có cashflow FEE âm (phí vào lệnh đã được ghi nhận)
- [ ] Net uPnL của position gần bằng 0

### Sau 24 giờ

- [ ] Có ít nhất 3 entries funding trong cashflow (3 kỳ × 8h)
- [ ] APR hiển thị hợp lý so với funding rate thị trường
- [ ] Equity tăng lên đúng bằng funding collected (nếu giá không đổi nhiều)

### Khi position CLOSED

- [ ] Status = CLOSED, không còn xuất hiện trong Open Positions
- [ ] uPnL = 0
- [ ] Total Realized PnL = Funding Earned − Fees Paid ± Basis PnL
- [ ] Số liệu xuất hiện đúng trong trang Closed Positions

---

## Phần 6: Dấu Hiệu Report Sai — Red Flags

| Hiện tượng trên dashboard | Nguyên nhân có thể | Cách xác nhận |
|---|---|---|
| uPnL 2 legs lệch nhau lớn (>1% notional) | Size mismatch hoặc giá bị stale | So sánh size 2 legs, kiểm tra timestamp của giá |
| APR > 200% | Notional quá nhỏ hoặc data lỗi | Kiểm tra `amount_usd` của position |
| Funding = $0 sau 24h | Cron bị dừng, API lỗi | Kiểm tra logs, kiểm tra Hyperliquid Funding History |
| Total Equity không khớp Hyperliquid UI | Thiếu 1 wallet hoặc snapshot cũ | Cộng cả 2 wallets trên Hyperliquid UI |
| Net Carry âm liên tục | Funding rate đảo chiều (rate âm) | Xem funding rate trên trang Market của Hyperliquid |
| Realized APR << Current APR | Có giai đoạn funding âm trước đó | Xem lịch sử cashflows theo từng ngày |
| Net uPnL lớn dương hoặc âm | Position không còn delta-neutral | Kiểm tra size spot vs perp có còn cân bằng không |

---

## Phần 7: Tóm Tắt Công Thức

| Metric | Công thức |
|---|---|
| Total Equity | `Σ accountValue` của tất cả wallets |
| uPnL (LONG) | `(giá hiện tại − giá vào) × size` |
| uPnL (SHORT) | `(giá vào − giá hiện tại) × size` |
| Funding Earned | Tổng các khoản nhận từ sàn mỗi 8h (dương) |
| Fees Paid | Tổng phí giao dịch (âm) |
| Net Funding | `Funding Earned − Fees Paid` |
| APR (gross) | `funding_rate_8h × 3 × 365 × 100%` |
| Realized APR | `(Net Funding / Vốn / Số ngày) × 365 × 100%` |
| Entry Basis | `(giá vào spot / giá vào perp) − 1` |
| Exit Basis | `(giá ra spot / giá ra perp) − 1` |
| Basis PnL | `(Exit Basis − Entry Basis) × 10,000 bps` |
| Net Delta | `Σ (size × sign)` — phải gần bằng 0 |
