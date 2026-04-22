# Fund Deployment Plan — 2026-04-20

**NAV:** $800,000  
**Review deadline:** 2026-04-21  
**Status:** Pending team approval

---

## 1. Tổng quan phân bổ danh mục

| Strategy | Tỉ trọng | Số tiền | Expected APR | Contribute APR |
|---|---|---|---|---|
| Felix USDC (Lending) | 50% | $400,000 | 6.00% | 3.00% |
| Felix USDC Frontier (Lending) | 40% | $320,000 | 18.00% | 7.20% |
| Delta Neutral — COST | 5% | $40,000 | 20.00% | 1.00% |
| Delta Neutral — ORCL | 5% | $40,000 | 15.00% | 0.75% |
| **Total** | **100%** | **$800,000** | | **11.95%** |

**Blended portfolio APR target: 11.95%**

---

## 2. Luận điểm phân bổ

### 2.1 Tại sao không deploy crypto delta neutral ngay lúc này

Sau khi scan toàn bộ 267 crypto candidates (snapshot 2026-04-20), thị trường crypto **không có candidate nào đủ điều kiện deploy ngay** theo tiêu chí:
- APR 7d > 11% AND APR 14d > 11%
- Positive funding share > 60%
- Không có DECAYING_REGIME

**Kết quả:** Chỉ có 7 candidates pass stable criteria, nhưng toàn bộ đều là **NON_EXECUTABLE** (thiếu spot market).

**Phân tích chi tiết các nhóm:**

| Nhóm | Tình trạng | Dữ liệu |
|---|---|---|
| BTC, ETH | Funding âm kéo dài | Thị trường tăng nhưng funding rate vẫn âm — traders long không muốn trả phí |
| LINK, BNB, AVAX | Executable nhưng APR thấp | LINK apr_7d=10.2%, BNB apr_7d=10.8%, AVAX apr_7d=9.5% — dưới ngưỡng 11% |
| XAU (Vàng) | Đang decay mạnh | apr_14d=34%, apr_7d=39% trông ổn định, nhưng apr_1d = **-182.8%** → DECAYING_REGIME, cần quan sát |
| SPACEX, APEX, MNT | Stable nhưng không trade được | NON_EXECUTABLE do thiếu spot market trên Hyperliquid |

**Kết luận:** Cơ hội cost hiện tại quá cao. Felix USDC Frontier đang trả **18% APR** — không có lý do kinh tế để deploy delta neutral crypto ở mức 10-11% trong khi lending không có rủi ro directional.

---

### 2.2 Lending pool — chiến lược chính (90% NAV)

**Felix USDC (50% — $400,000)**
- APR: 6% → Contribute 3% vào blended return
- Rủi ro thấp nhất trong danh mục, capital luôn sẵn sàng rút để redeploy

**Felix USDC Frontier (40% — $320,000)**
- APR: 18% → Contribute 7.2% vào blended return
- Cao hơn hầu hết crypto delta neutral opportunities hiện tại
- Lending pool là buffer chiến lược: khi lãi suất giảm xuống dưới 5%, sẽ rotate sang delta neutral

---

### 2.3 Delta Neutral Felix Equities — pilot allocation (10% NAV)

Trong context crypto flat/âm, **Felix Equities là ngoại lệ duy nhất** có yield ổn định và executable. Hai candidates pass toàn bộ tiêu chí:

#### COST (Costco) — 5% / $40,000

| Metric | Giá trị |
|---|---|
| Expected APR (eff_apr) | **20.43%** |
| APR 7d | 64.18% |
| APR 14d | 40.87% |
| Positive share | 71.4% |
| Quality score | 57.41 |
| Status | EXECUTABLE |

> **Luận điểm:** COST có funding rate duy trì ở mức rất cao và consistent. Eff APR = 20.43% là con số conservative (= apr_14d / 2), tức là ngay cả khi điều chỉnh về nửa mức trung bình 14 ngày vẫn outperform lending rate USDC. APR 7d (64%) và APR 14d (40.87%) đều ổn định và không có dấu hiệu decay.

#### ORCL (Oracle) — 5% / $40,000

| Metric | Giá trị |
|---|---|
| Expected APR (apr_14d) | **15.70%** |
| APR 7d | 21.12% |
| APR 14d | 15.70% |
| Positive share | 86.8% |
| Quality score | 52.94 |
| Status | EXECUTABLE |

> **Luận điểm:** ORCL có positive share cao nhất trong nhóm equities stable (86.8%), funding đều và nhất quán. APR 7d và APR 14d converge gần nhau (21% vs 15.7%) — đây là dấu hiệu của trend ổn định, không spike. Expected APR 15% lấy theo apr_14d.

---

## 3. Điều kiện review và re-deploy

### Trigger để rotate từ lending sang delta neutral

| Điều kiện | Action |
|---|---|
| Felix USDC APR giảm xuống **< 5%** | Evaluate deploy thêm delta neutral crypto |
| Xuất hiện crypto candidate với apr_7d > 15% + stable + EXECUTABLE | Xem xét allocate thêm 5-10% |
| XAU (Gold) phục hồi, apr_1d dương 3 ngày liên tiếp | Re-evaluate XAU position |

### Điều kiện thoát Felix Equities

| Position | Exit signal |
|---|---|
| COST | apr_7d giảm xuống < 15% hoặc DECAYING_REGIME xuất hiện |
| ORCL | apr_7d giảm xuống < 11% hoặc DECAYING_REGIME xuất hiện |

---

## 4. Candidate screening data (2026-04-20)

Dữ liệu đầy đủ từ candidate scan ngày hôm nay:

### Crypto Candidates — Top 20 (Non-Felix)

> Stable criteria: apr_7d > 11% AND apr_14d > 11% AND positive_share > 60% AND no DECAYING_REGIME

| # | Symbol | Venue | Stable | Quality | Pos% | Eff APR | APR 1d | APR 3d | APR 7d | APR 14d | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SPACEX | hyperliquid | YES | 62.27 | 100.0 | 9.70 | 18.03 | 20.38 | 21.40 | 19.39 | NON_EXECUTABLE |
| 2 | APEX | hyperliquid | YES | 59.79 | 100.0 | 6.38 | 10.95 | 11.25 | 12.86 | 12.77 | NON_EXECUTABLE |
| 3 | MNT | hyperliquid | YES | 56.18 | 99.9 | 5.62 | 10.95 | 11.54 | 11.31 | 11.24 | NON_EXECUTABLE |
| 4 | SMSN | tradexyz | YES | 54.81 | 62.7 | 46.41 | 291.84 | 177.37 | 94.67 | 92.81 | NON_EXECUTABLE |
| 5 | CRWV | tradexyz | YES | 54.30 | 73.7 | 14.92 | 172.62 | 55.65 | 48.70 | 29.84 | NON_EXECUTABLE |
| 6 | SKHX | tradexyz | YES | 50.89 | 66.3 | 34.76 | 27.37 | 170.47 | 105.59 | 69.53 | NON_EXECUTABLE |
| 7 | LIT | hyperliquid | YES | 49.94 | 87.5 | 6.58 | 10.91 | 9.59 | 16.35 | 13.15 | NON_EXECUTABLE |
| 8 | LINK | hyperliquid | low_apr | 66.56 | 95.4 | 4.57 | 7.38 | 9.94 | 10.18 | 9.15 | EXECUTABLE |
| 9 | BNB | hyperliquid | low_apr | 66.00 | 83.0 | 4.82 | 8.12 | 10.15 | 10.77 | 9.65 | EXECUTABLE |
| 10 | AVAX | hyperliquid | low_apr | 64.97 | 89.9 | 4.66 | 1.56 | 5.99 | 9.49 | 9.33 | EXECUTABLE |
| 11 | CFX | hyperliquid | low_apr | 64.61 | 100.0 | 5.47 | 10.95 | 10.95 | 10.95 | 10.95 | EXECUTABLE |
| 12 | PAXG | hyperliquid | low_apr | 64.01 | 89.8 | 5.42 | 10.61 | 10.85 | 10.92 | 10.84 | NON_EXECUTABLE |
| 13 | XAU | kinetiq | **decay** | 62.74 | 96.2 | 17.16 | **-182.80** | 25.15 | 39.38 | 34.33 | NON_EXECUTABLE |
| 14 | AAVE | hyperliquid | low_apr | 61.91 | 89.4 | 4.79 | 3.83 | 8.24 | 10.35 | 9.58 | EXECUTABLE |
| 15 | DOGE | hyperliquid | low_apr | 61.31 | 75.8 | 3.45 | 7.02 | 7.98 | 9.41 | 6.89 | NON_EXECUTABLE |
| 16 | TRX | hyperliquid | low_apr | 60.88 | 83.9 | 3.61 | 5.64 | 8.45 | 8.41 | 7.22 | NON_EXECUTABLE |
| 17 | FIL | hyperliquid | low_apr | 60.84 | 89.2 | 5.44 | 10.95 | 10.95 | 10.95 | 10.88 | NON_EXECUTABLE |
| 18 | UNI | hyperliquid | low_apr | 60.59 | 84.0 | 3.17 | 10.41 | 10.80 | 8.88 | 6.34 | NON_EXECUTABLE |
| 19 | MON | hyperliquid | low_apr | 58.61 | 92.7 | 5.74 | 7.45 | 9.61 | 10.88 | 11.48 | EXECUTABLE |
| 20 | LTC | hyperliquid | low_apr | 57.83 | 75.9 | 2.76 | 6.97 | 6.21 | 6.75 | 5.52 | NON_EXECUTABLE |

### Felix Equities Candidates — Top 20 (weekday-only data)

| # | Symbol | Venue | Stable | Quality | Pos% | Eff APR | APR 1d | APR 3d | APR 7d | APR 14d | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **COST** | tradexyz | **YES** | 57.41 | 71.4 | 20.43 | 32.29 | 161.95 | 64.18 | 40.87 | EXECUTABLE |
| 2 | **ORCL** | tradexyz | **YES** | 52.94 | 86.8 | 7.85 | 34.67 | 5.33 | 21.12 | 15.70 | EXECUTABLE |
| 3 | AMD | tradexyz | low_apr | 53.03 | 95.0 | 4.73 | 66.87 | 15.24 | 10.03 | 9.46 | EXECUTABLE |
| 4 | BABA | tradexyz | low_apr | 52.45 | 91.4 | 5.39 | 45.16 | 31.77 | 15.80 | 10.79 | EXECUTABLE |
| 5 | NVDA | kinetiq | low_apr | 51.29 | 99.3 | 2.68 | 43.73 | 7.58 | 5.35 | 5.35 | EXECUTABLE |
| 6 | AAPL | kinetiq | low_apr | 50.24 | 91.2 | 1.84 | -6.24 | 1.79 | 4.27 | 3.68 | EXECUTABLE |
| 7 | BABA | kinetiq | low_apr | 49.32 | 91.2 | 1.29 | 34.17 | 7.47 | 5.87 | 2.57 | EXECUTABLE |
| 8 | AAPL | tradexyz | low_apr | 47.74 | 94.0 | 4.06 | 21.06 | 9.93 | 7.67 | 8.13 | EXECUTABLE |
| 9 | META | tradexyz | low_apr | 46.22 | 87.5 | 4.63 | 45.51 | 16.91 | 9.99 | 9.26 | EXECUTABLE |
| 10 | HIMS | tradexyz | decay | 43.81 | 76.0 | 53.01 | -25.48 | 68.65 | 163.49 | 106.01 | EXECUTABLE |
| 11 | RIVN | tradexyz | decay | 43.45 | 84.9 | 15.99 | -13.45 | 75.81 | 42.26 | 31.99 | EXECUTABLE |
| 12 | TSLA | kinetiq | low_apr | 43.28 | 94.2 | 2.34 | 87.38 | 9.95 | 5.96 | 4.69 | EXECUTABLE |
| 13 | NVDA | tradexyz | low_apr | 41.73 | 68.9 | 1.43 | 11.04 | 5.85 | 2.85 | 2.85 | EXECUTABLE |
| 14 | NFLX | tradexyz | low_apr | 39.77 | 91.5 | 3.42 | 54.46 | 3.22 | 6.86 | 6.83 | EXECUTABLE |
| 15 | GOOGL | tradexyz | low_apr | 38.64 | 89.3 | 2.15 | 19.82 | 17.56 | 8.15 | 4.30 | EXECUTABLE |
| 16 | MSFT | tradexyz | low_apr,decay | 38.15 | 96.0 | 5.78 | 33.43 | 5.58 | 10.43 | 11.56 | EXECUTABLE |
| 17 | MU | tradexyz | decay | 37.04 | 90.5 | 8.51 | 4.35 | 8.09 | 13.92 | 17.01 | EXECUTABLE |
| 18 | GOOGL | kinetiq | low_apr,decay | 36.27 | 89.3 | 3.98 | 91.69 | 29.77 | 10.59 | 7.97 | EXECUTABLE |
| 19 | CRCL | tradexyz | low_apr,decay | 34.24 | 91.2 | 5.85 | -62.00 | -28.02 | 9.92 | 11.70 | EXECUTABLE |
| 20 | BMNR | kinetiq | low_apr,decay | 24.92 | 83.6 | 5.12 | 620.59 | 37.92 | 5.04 | 10.24 | EXECUTABLE |

---

## 5. Quyết định cần team xác nhận

- [ ] Approve phân bổ 90% NAV vào Lending (Felix USDC + Frontier)
- [ ] Approve pilot 5% COST delta neutral ($40,000)
- [ ] Approve pilot 5% ORCL delta neutral ($40,000)
- [ ] Xác nhận review trigger: Felix USDC drops < 5% → họp lại để quyết định rotate
