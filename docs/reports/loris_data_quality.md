# Loris Funding Data Quality Report

**Generated:** 2026-04-20 04:09 UTC  
**CSV path:** `data/loris_funding_history.csv`  
**CSV latest row:** 2026-04-20 03:51 UTC  
**Staleness threshold:** 12h  
**Gap threshold:** 2 days  

> **STATUS: ISSUES FOUND** — 42 stale symbols, 250 gap events, 29 low-sample symbols.

## Venue Summary

| Venue | Symbols | Total Rows | Date Range | Stale (>12h) | With Gaps (>2d) |
|-------|---------|------------|------------|--------|-----------|
| felix | 14 | 15,438 | 2026-01-19 → 2026-04-20 | 1 | 13 |
| hyena | 24 | 29,411 | 2026-01-19 → 2026-04-20 | 0 | 22 |
| hyperliquid | 135 | 168,903 | 2025-12-12 → 2026-04-20 | 26 | 116 |
| kinetiq | 24 | 24,876 | 2026-01-19 → 2026-04-20 | 5 | 22 |
| tradexyz | 62 | 58,508 | 2026-01-19 → 2026-04-20 | 10 | 45 |

## Felix Equity Coverage

- **Total Felix equities defined:** 205
- **Symbols with data in CSV (any venue):** 26
- **Symbols MISSING from CSV (all venues):** 179

Missing symbols (no rows in any venue):

`AAL`, `ABBV`, `ABNB`, `ABT`, `ACHR`, `ACN`, `ADBE`, `ADI`, `AGG`, `AMAT`
`AMC`, `AMGN`, `ANET`, `APO`, `APP`, `ARM`, `ASML`, `AVGO`, `AXP`, `BA`
`BAC`, `BBAI`, `BIDU`, `BILI`, `BINC`, `BLK`, `BLSH`, `BTG`, `BTGO`, `BZ`
`C`, `CAT`, `CEG`, `CIFR`, `CLOA`, `CLOI`, `CMG`, `COF`, `COIN`, `COP`
`COPX`, `CPNG`, `CRM`, `CRWD`, `CSCO`, `CVNA`, `CVX`, `DBC`, `DE`, `DGRW`
`DIS`, `DNN`, `EEM`, `EFA`, `EQIX`, `ETHA`, `F`, `FIG`, `FIGR`, `FSOL`
`FTGC`, `FUTU`, `GE`, `GEMI`, `GLD`, `GRAB`, `GRND`, `GS`, `HD`, `HYG`
`IAU`, `IBIT`, `IBM`, `IEFA`, `IEMG`, `IJH`, `INTU`, `IREN`, `ISRG`, `ITOT`
`IVV`, `IWF`, `IWM`, `IWN`, `JAAA`, `JD`, `JNJ`, `JPM`, `KLAC`, `KO`
`LI`, `LIN`, `LMT`, `LOW`, `LRCX`, `MA`, `MARA`, `MCD`, `MELI`, `MP`
`MRK`, `MRNA`, `MTZ`, `NEE`, `NIKL`, `NIO`, `NKE`, `NOW`, `NTES`, `NVO`
`OKLO`, `ON`, `ONDS`, `OPEN`, `OPRA`, `OSCR`, `OXY`, `PALL`, `PANW`, `PBR`
`PCG`, `PDBC`, `PDD`, `PEP`, `PFE`, `PG`, `PINS`, `PLTR`, `PLUG`, `PSQ`
`PYPL`, `QBTS`, `QCOM`, `QQQ`, `RDDT`, `REMX`, `RGTI`, `RIOT`, `SBET`, `SBUX`
`SCHW`, `SGOV`, `SHOP`, `SLV`, `SMCI`, `SNAP`, `SNOW`, `SO`, `SOFI`, `SOUN`
`SPGI`, `SPOT`, `SPY`, `SQQQ`, `T`, `TCOM`, `TIP`, `TLN`, `TLT`, `TM`
`TMO`, `TMUS`, `TQQQ`, `TXN`, `UBER`, `UNH`, `USFR`, `USO`, `V`, `VRT`
`VST`, `VTI`, `VTV`, `VZ`, `WFC`, `WMT`, `WULF`, `XOM`, `XYZ`

## Stale Symbols (latest row > 12h ago)

| Venue | Symbol | Last Row | Hours Stale |
|-------|--------|----------|-------------|
| kinetiq | SPACEX | 2026-01-20 16:00 UTC | 2148.2h |
| hyperliquid | SNX | 2026-03-09 15:25 UTC | 996.7h |
| hyperliquid | SKR | 2026-03-10 04:00 UTC | 984.2h |
| hyperliquid | AZTEC | 2026-03-12 16:03 UTC | 924.1h |
| hyperliquid | BABY | 2026-03-12 16:03 UTC | 924.1h |
| hyperliquid | SPX | 2026-03-12 16:03 UTC | 924.1h |
| tradexyz | EWJ | 2026-03-19 13:37 UTC | 758.5h |
| hyperliquid | POLYX | 2026-03-19 14:37 UTC | 757.5h |
| hyperliquid | KAS | 2026-03-21 03:07 UTC | 721.0h |
| felix | USA500 | 2026-03-21 15:37 UTC | 708.5h |
| kinetiq | US500 | 2026-03-21 15:37 UTC | 708.5h |
| hyperliquid | IMX | 2026-03-22 13:37 UTC | 686.5h |
| tradexyz | META | 2026-03-26 00:44 UTC | 603.4h |
| hyperliquid | ANIME | 2026-03-27 02:42 UTC | 577.5h |
| hyperliquid | FOGO | 2026-03-28 15:11 UTC | 541.0h |
| hyperliquid | PROVE | 2026-03-31 01:30 UTC | 482.7h |
| hyperliquid | RESOLV | 2026-03-31 01:30 UTC | 482.7h |
| kinetiq | GOOGL | 2026-03-31 01:30 UTC | 482.7h |
| tradexyz | GOOGL | 2026-03-31 01:30 UTC | 482.7h |
| hyperliquid | ENS | 2026-04-01 02:48 UTC | 457.4h |
| kinetiq | AAPL | 2026-04-01 02:48 UTC | 457.4h |
| tradexyz | AAPL | 2026-04-01 02:48 UTC | 457.4h |
| tradexyz | TSM | 2026-04-01 02:48 UTC | 457.4h |
| hyperliquid | SUPER | 2026-04-09 06:00 UTC | 262.2h |
| hyperliquid | LINEA | 2026-04-09 17:30 UTC | 250.7h |
| tradexyz | AMZN | 2026-04-10 14:30 UTC | 229.7h |
| hyperliquid | TNSR | 2026-04-10 18:00 UTC | 226.2h |
| hyperliquid | MET | 2026-04-11 17:00 UTC | 203.2h |
| kinetiq | MU | 2026-04-13 03:00 UTC | 169.2h |
| tradexyz | MU | 2026-04-13 03:00 UTC | 169.2h |
| tradexyz | SNDK | 2026-04-13 03:00 UTC | 169.2h |
| tradexyz | EWY | 2026-04-13 13:00 UTC | 159.2h |
| tradexyz | NATGAS | 2026-04-15 00:00 UTC | 124.2h |
| hyperliquid | WCT | 2026-04-16 02:30 UTC | 97.7h |
| hyperliquid | PEOPLE | 2026-04-16 20:30 UTC | 79.7h |
| hyperliquid | MOODENG | 2026-04-17 05:00 UTC | 71.2h |
| hyperliquid | TURBO | 2026-04-17 06:00 UTC | 70.2h |
| hyperliquid | MERL | 2026-04-17 07:00 UTC | 69.2h |
| hyperliquid | CFX | 2026-04-17 07:30 UTC | 68.7h |
| hyperliquid | GRASS | 2026-04-17 07:30 UTC | 68.7h |
| hyperliquid | STX | 2026-04-17 07:30 UTC | 68.7h |
| hyperliquid | TST | 2026-04-17 07:30 UTC | 68.7h |

## Gap Report (gaps > 2 days within a series)

| Venue | Symbol | Gap Start | Gap End | Gap (hours) |
|-------|--------|-----------|---------|-------------|
| hyperliquid | MOODENG | 2026-03-18 12:07 UTC | 2026-04-16 04:00 UTC | 687.9h |
| hyperliquid | MOVE | 2026-03-21 00:11 UTC | 2026-04-16 00:00 UTC | 623.8h |
| felix | NVDA | 2026-03-26 00:44 UTC | 2026-04-12 03:30 UTC | 410.8h |
| kinetiq | NVDA | 2026-03-26 00:44 UTC | 2026-04-12 03:30 UTC | 410.8h |
| tradexyz | NVDA | 2026-03-26 00:44 UTC | 2026-04-12 03:30 UTC | 410.8h |
| hyperliquid | MET | 2026-03-12 16:03 UTC | 2026-03-28 15:11 UTC | 383.1h |
| hyperliquid | W | 2026-03-31 01:30 UTC | 2026-04-16 00:00 UTC | 382.5h |
| hyperliquid | AR | 2026-04-01 02:48 UTC | 2026-04-15 18:30 UTC | 351.7h |
| hyperliquid | MET | 2026-03-28 15:11 UTC | 2026-04-11 12:30 UTC | 333.3h |
| hyperliquid | SUPER | 2026-03-27 02:42 UTC | 2026-04-09 03:00 UTC | 312.3h |
| hyperliquid | STX | 2026-04-01 02:48 UTC | 2026-04-14 00:00 UTC | 309.2h |
| hyena | BASED | 2026-04-01 02:48 UTC | 2026-04-12 06:30 UTC | 267.7h |
| hyperliquid | CFX | 2026-04-01 02:48 UTC | 2026-04-10 05:30 UTC | 218.7h |
| hyperliquid | GRASS | 2026-04-01 02:48 UTC | 2026-04-09 22:30 UTC | 211.7h |
| tradexyz | NATGAS | 2026-04-01 02:48 UTC | 2026-04-09 20:00 UTC | 209.2h |
| hyperliquid | TURBO | 2026-04-01 02:48 UTC | 2026-04-09 18:00 UTC | 207.2h |
| felix | USA100 | 2026-04-01 02:48 UTC | 2026-04-09 03:00 UTC | 192.2h |
| felix | USDE | 2026-04-01 02:48 UTC | 2026-04-09 03:00 UTC | 192.2h |
| hyperliquid | ASTER | 2026-04-01 02:48 UTC | 2026-04-09 03:00 UTC | 192.2h |
| hyperliquid | SKY | 2026-04-01 02:48 UTC | 2026-04-09 03:00 UTC | 192.2h |
| tradexyz | GME | 2026-04-01 02:48 UTC | 2026-04-09 03:00 UTC | 192.2h |
| tradexyz | LLY | 2026-04-01 02:48 UTC | 2026-04-09 03:00 UTC | 192.2h |
| hyperliquid | STX | 2026-03-11 08:02 UTC | 2026-03-18 21:07 UTC | 181.1h |
| hyperliquid | TURBO | 2026-04-09 20:30 UTC | 2026-04-16 17:30 UTC | 165.0h |
| tradexyz | EWY | 2026-03-12 16:03 UTC | 2026-03-19 04:37 UTC | 156.6h |
| felix | BTC | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | CL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | CRCL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | NVDA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | PLATINUM | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | TSLA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | USA100 | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | USA500 | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | USDE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | XAG | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | XAU | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | XCU | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| felix | XMR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | ADA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | BCH | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | BNB | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | BTC | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | DOGE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | ENA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | ETH | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | FARTCOIN | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | HYPE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | IP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | LINK | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | LIT | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | LTC | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | PEPE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | PUMP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | SOL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | SUI | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | XMR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | XPL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | XRP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyena | ZEC | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ADA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | AERO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ALGO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | APE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | APEX | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | APT | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | AR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ARB | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ASTER | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ATOM | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | AVAX | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | AVNT | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | AXS | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | BCH | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | BERA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | BIO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | BLAST | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | BNB | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | BONK | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | BTC | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | CAKE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | CC | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | CFX | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | COMP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | CRV | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | DASH | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | DOGE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | DOT | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | DYDX | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | EIGEN | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ENA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ENS | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ETC | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ETH | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ETHFI | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | FARTCOIN | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | FET | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | FIL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | FLOKI | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | FOGO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | FTT | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | GALA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | GRASS | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | HBAR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | HYPE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ICP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | INJ | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | IP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | JTO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | JUP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | KAITO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | LDO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | LINEA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | LINK | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | LIT | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | LTC | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | LUNC | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | MNT | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | MON | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | MORPHO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | MOVE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | NEAR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | NEO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | NXPC | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ONDO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | OP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ORDI | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | PAXG | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | PENDLE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | PENGU | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | PEPE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | PNUT | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | POL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | PUMP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | PURR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | PYTH | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | RENDER | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | RESOLV | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | S | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | SAND | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | SEI | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | SHIB | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | SKY | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | SOL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | STABLE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | STRK | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | SUI | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | SYRUP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | TAO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | TIA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | TON | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | TRB | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | TRUMP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | TRX | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | UNI | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | VIRTUAL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | VVV | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | WIF | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | WLD | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | WLFI | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | XLM | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | XMR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | XPL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | XRP | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | YZY | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ZEC | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ZEN | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ZK | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | ZRO | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | AAPL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | BABA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | BMNR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | CL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | EUR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | GLDMINE | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | GOOGL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | JPN225 | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | MU | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | NVDA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | RTX | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | SEMI | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | SMALL2000 | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | TENCENT | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | TSLA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | US500 | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | USBOND | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | USENERGY | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | USTECH | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | XAG | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | XAU | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| kinetiq | XIAOMI | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | AAPL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | AMD | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | BABA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | BRENTOIL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | CL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | COST | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | CRCL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | CRWV | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | DXY | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | EUR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | EWJ | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | GME | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | GOOGL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | HYUNDAI | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | JP225 | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | JPY | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | KIOXIA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | KR200 | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | LLY | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | META | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | MSFT | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | MSTR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | MU | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | NATGAS | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | NFLX | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | NVDA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | ORCL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | PLATINUM | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | RIVN | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | SKHX | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | SMSN | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | SNDK | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | SOFTBANK | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | TSLA | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | TSM | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | URANIUM | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | URNM | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | USAR | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | VIX | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | XAG | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | XAL | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | XAU | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | XCU | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| tradexyz | XYZ100 | 2026-03-12 16:03 UTC | 2026-03-18 04:20 UTC | 132.3h |
| hyperliquid | STX | 2026-03-26 00:44 UTC | 2026-03-31 01:30 UTC | 120.8h |
| hyperliquid | W | 2026-03-26 00:44 UTC | 2026-03-31 01:30 UTC | 120.8h |
| kinetiq | GOOGL | 2026-03-26 00:44 UTC | 2026-03-31 01:30 UTC | 120.8h |
| tradexyz | GOOGL | 2026-03-26 00:44 UTC | 2026-03-31 01:30 UTC | 120.8h |
| hyperliquid | ENS | 2026-03-21 17:07 UTC | 2026-03-26 00:44 UTC | 103.6h |
| tradexyz | EWY | 2026-03-19 05:07 UTC | 2026-03-23 03:35 UTC | 94.5h |
| tradexyz | EWY | 2026-03-23 06:07 UTC | 2026-03-27 01:23 UTC | 91.3h |
| hyperliquid | ENS | 2026-03-28 15:11 UTC | 2026-04-01 02:48 UTC | 83.6h |
| hyperliquid | AR | 2026-03-19 06:07 UTC | 2026-03-22 15:37 UTC | 81.5h |
| hyperliquid | IMX | 2026-03-18 23:07 UTC | 2026-03-22 02:07 UTC | 75.0h |
| hyperliquid | AVNT | 2026-04-13 00:00 UTC | 2026-04-16 00:00 UTC | 72.0h |
| hyperliquid | LINEA | 2026-03-26 00:44 UTC | 2026-03-28 15:11 UTC | 62.4h |
| hyperliquid | COMP | 2026-03-28 15:11 UTC | 2026-03-31 01:30 UTC | 58.3h |
| tradexyz | NATGAS | 2026-04-12 12:30 UTC | 2026-04-14 20:00 UTC | 55.5h |
| hyperliquid | CFX | 2026-04-13 20:00 UTC | 2026-04-16 02:00 UTC | 54.0h |
| hyperliquid | AR | 2026-03-30 02:38 UTC | 2026-04-01 02:48 UTC | 48.2h |

## Low Sample (< 16 rows in last 14 days)

| Venue | Symbol | Rows (14d) |
|-------|--------|------------|
| felix | USA500 | 0 |
| hyperliquid | ANIME | 0 |
| hyperliquid | AZTEC | 0 |
| hyperliquid | BABY | 0 |
| hyperliquid | ENS | 0 |
| hyperliquid | FOGO | 0 |
| hyperliquid | IMX | 0 |
| hyperliquid | KAS | 0 |
| hyperliquid | POLYX | 0 |
| hyperliquid | PROVE | 0 |
| hyperliquid | RESOLV | 0 |
| hyperliquid | SKR | 0 |
| hyperliquid | SNX | 0 |
| hyperliquid | SPX | 0 |
| kinetiq | AAPL | 0 |
| kinetiq | GOOGL | 0 |
| kinetiq | SPACEX | 0 |
| kinetiq | US500 | 0 |
| tradexyz | AAPL | 0 |
| tradexyz | EWJ | 0 |
| tradexyz | GOOGL | 0 |
| tradexyz | META | 0 |
| tradexyz | TSM | 0 |
| tradexyz | AMZN | 4 |
| hyperliquid | WCT | 5 |
| hyperliquid | PEOPLE | 7 |
| hyperliquid | SUPER | 7 |
| hyperliquid | MERL | 9 |
| hyperliquid | MET | 10 |
