#!/usr/bin/env python3
"""
HypurrFi market rates CLI — fetch live supply/borrow APYs, TVL, utilization,
caps, and liquidity for all HypurrFi markets on HyperEVM.

Usage:
    python3 hypurrfi_rates.py [--market {pooled,prime,yield,scale,earn,all}]
                              [--json] [--address 0x...] [--rpc URL]

Requirements: Python 3.9+ stdlib only (no pip installs needed)
"""

import argparse
import dataclasses
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

# ── CONSTANTS ────────────────────────────────────────────────────────────────

DEFAULT_RPC = "https://rpc.hyperliquid.xyz/evm"
SECS_PER_YEAR = 365 * 24 * 3600

# Contract addresses
POOLED_DATA_PROVIDER = "0x895C799a5bbdCb63B80bEE5BD94E7b9138D977d6"
AAVE_POOL = "0xceCcE0EB9DD2Ef7996e01e25DD70e461F918A14b"

# Verified 4-byte function selectors
SEL = {
    # Aave ProtocolDataProvider
    "getAllReservesTokens":         "0xb316ff89",
    "getReserveData":              "0x35ea6a75",
    "getReserveConfigurationData": "0x3e150141",
    "getReserveCaps":              "0x46fbe558",
    "getUserReserveData":          "0x28dd2d01",
    # Aave Pool
    "getUserAccountData":          "0xbf92857c",
    # Euler IEVault (no args)
    "totalAssets":   "0x01e1d114",
    "totalBorrows":  "0x47bd3718",
    "cash":          "0x961be391",
    "interestRate":  "0x587f5ed7",
    "totalSupply":   "0x18160ddd",
    "decimals":      "0x313ce567",
    "asset":         "0x38d52e0f",
    "symbol":        "0x95d89b41",
    "reserveFee":    "0x960b26a2",
    # Euler IEVault (address arg)
    "balanceOf":     "0x70a08231",
    "maxWithdraw":   "0xce96cb77",
}

# Vault address maps (symbol → vault contract address)
PRIME_VAULTS: dict[str, str] = {
    "WHYPE":  "0xf73c654d468f5485bf15f3470b78851a49257704",
    "kHYPE":  "0x443100d1149d6d925edb044248bbe32c5c7ae955",
    "UBTC":   "0x8a4545827df5446ba120b904e5306e58acca4e89",
    "USDC":   "0xc200aab602cd7046389b5c8fb088884323f8dd0f",
    "USDT0":  "0x28fca2611d1dd8109c26f748cd2cf3bb4fc6d2cd",
    "USDH":   "0x83c34784e355ad2670db77623b845273844fa480",
}

YIELD_VAULTS: dict[str, str] = {
    "WHYPE":    "0xc7e7861352df6919e7152c007832c48a777f2a4c",
    "kHYPE":    "0x97d30b40048ba3fc6b6628ce5e02e77f35b64fe0",
    "PT-kHYPE": "0x3403176f548400772c39e64564f2b148bcdfb65e",
    "wstHYPE":  "0x64a3052570f5a1c241c6c8cd32f8f9ad411e6990",
    "lstHYPE":  "0x1739105522e4fc9675f857c859223d24dfe7593c",
    "beHYPE":   "0xcAAA9A6e543b9af588Dce91E6c35Cb5fa1c7734C",
    "UBTC":     "0x61Cb3b093b7125D593CCfa135C6e4E9D52D2e697",
    "UETH":     "0x06bf901Ce21450Bab46ceA74C4Bb6F07E6859CD6",
    "USDH":     "0x09a6ad87Eff280755BdF3E2C863358D27d81262D",
    "USDT0":    "0x94F5C76A93F12057d73991AE5B4f70e9287b5b28",
    "USDC":     "0xf9bb65e113418292d1a3555515fbd64637a0be18",
    "whHYPE":   "0xBb7DC37dbc108d40BcdD60403EF7bFDD6489071E",
    "LHYPE":    "0x23bf20b4d6E280eacA58826a541c9ee5401BD357",
}

SCALE_VAULTS: dict[str, str] = {
    "USDXL":  "0xd62e7c9e6b1e43cb06e1ba46243b128c81bc918c",
    "PURR":   "0x0e8724954a5b2ca41146f11bd6008fbeeae50603",
    "UFART":  "0xb2d7b74ff64e5f4908256e1c17487939f2435155",
    "UPUMP":  "0x1ba03af962c99b36297e31f56b41be31c37452d5",
    "bbHLP":  "0x6e02c17eb84e2b02a4cb93c086091d50ee74c16e",
    "haHYPE": "0x8231b0c73a265d745e6810bffeed83b6ed1501fb",
}

EARN_VAULTS: dict[str, str] = {
    "purrUSDH":  "0xf38ea9de758a8f6be08b6e65bc0ff2f3e3ab741b",
    "purrHYPE":  "0xe8b10461ea0b04ff30f4cbfc3e93957cac00ded4",
    "purrUSDT0": "0x6dd448d5cb73dc96788d5be605dd3c5c83864a36",
    "purrUSDC":  "0xf868a2b30854fe13e26f7ab7a92609ccb6b9c0e1",
}


# ── JSON-RPC CLIENT ───────────────────────────────────────────────────────────

class JsonRpcClient:
    def __init__(self, rpc_url: str, timeout: int = 15):
        self.rpc_url = rpc_url
        self.timeout = timeout
        self._id = 0

    def eth_call(self, to: str, data: str) -> Optional[str]:
        self._id += 1
        payload = json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": to, "data": data}, "latest"],
            "id": self._id,
        }).encode()
        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    self.rpc_url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout * (attempt + 1)) as resp:
                    body = json.loads(resp.read())
                    result = body.get("result")
                    if result and result != "0x":
                        return result
                    return None
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                if attempt == 0:
                    print(f"[warn] RPC error ({exc}), retrying...", file=sys.stderr)
                    time.sleep(0.5)
                else:
                    print(f"[error] RPC call failed: {exc}", file=sys.stderr)
        return None


# ── ABI CODEC ────────────────────────────────────────────────────────────────

def encode_address(addr: str) -> str:
    """Pad a 20-byte address to 32-byte ABI word."""
    return addr.lower().replace("0x", "").zfill(64)

def _words(raw: Optional[str]) -> list[int]:
    if not raw:
        return []
    data = raw.replace("0x", "")
    return [int(data[i:i+64], 16) for i in range(0, len(data), 64) if len(data[i:i+64]) == 64]

def decode_uint256(raw: Optional[str], word_index: int) -> Optional[int]:
    w = _words(raw)
    return w[word_index] if word_index < len(w) else None

def decode_uint8(raw: Optional[str], word_index: int) -> Optional[int]:
    return decode_uint256(raw, word_index)

def decode_address(raw: Optional[str], word_index: int) -> Optional[str]:
    w = _words(raw)
    if word_index >= len(w):
        return None
    return "0x" + hex(w[word_index])[2:].zfill(40)

def decode_string_at_offset(data: str, offset_bytes: int) -> str:
    """Decode ABI-encoded string starting at byte offset."""
    hex_data = data.replace("0x", "")
    start = offset_bytes * 2
    length = int(hex_data[start:start+64], 16)
    str_hex = hex_data[start+64:start+64 + length*2]
    return bytes.fromhex(str_hex).decode("utf-8", errors="replace").strip("\x00")

def decode_token_array(raw: Optional[str]) -> list[tuple[str, str]]:
    """Decode (string symbol, address token)[] from getAllReservesTokens().

    ABI layout (verified against HyperEVM):
      byte  0-31: outer offset = 0x20 (points to array)
      byte 32-63: array length N
      byte 64-64+N*32-1: N offset values (each relative to byte 64 = start of head section)
      byte 64+offset[i]: tuple[i] = [str_offset_in_tuple (32), address (32),
                                      str_len (32), str_data (32, padded)]
    """
    if not raw:
        return []
    hd = raw.replace("0x", "")
    try:
        arr_len = int(hd[64:128], 16)
        HEAD_BYTE = 64  # offsets are relative to byte 64 (after length word)
        results = []
        for i in range(arr_len):
            # Offset word at byte 64 + i*32
            off_hex = (64 + i * 32) * 2
            tuple_offset = int(hd[off_hex:off_hex + 64], 16)
            # Tuple starts at byte HEAD_BYTE + tuple_offset
            tb = (HEAD_BYTE + tuple_offset) * 2  # hex char position
            # Word 0: string offset within tuple (always 64 = 2 words)
            str_off = int(hd[tb:tb + 64], 16)
            # Word 1: address (right-aligned in 32-byte word)
            addr = "0x" + hd[tb + 64:tb + 128][-40:]
            # String at tuple_start + str_off
            sb = tb + str_off * 2
            str_len = int(hd[sb:sb + 64], 16)
            symbol = bytes.fromhex(hd[sb + 64:sb + 64 + str_len * 2]).decode("utf-8", errors="replace")
            results.append((symbol, addr))
        return results
    except Exception as exc:
        print(f"[warn] decode_token_array failed: {exc}", file=sys.stderr)
        return []


# ── RATE MATH ─────────────────────────────────────────────────────────────────

def ray_to_apy_pct(rate_ray: Optional[int]) -> Optional[float]:
    if rate_ray is None or rate_ray == 0:
        return 0.0
    return rate_ray / 1e27 * 100.0

def euler_rate_to_apy_pct(rate: Optional[int]) -> Optional[float]:
    """Convert Euler per-second interest rate to annual APY %.

    Two observed scales across HypurrFi vaults (empirically verified):
      - Stablecoin vaults: rate ~ 1e8 range  → divide by 1e18 (per-second in 1e-18 units)
      - All other vaults:  rate ~ 1e18 range → divide by 1e27 (per-second in 1e-27 units)
    Threshold 1e12 cleanly separates the two groups.
    Upper bound 1e25 guards against accumulated index values (>= 1e27 typically).
    """
    if rate is None or rate == 0:
        return 0.0
    try:
        if rate < 1_000_000_000_000:  # < 1e12: stablecoin vaults
            r = rate / 1e18
        elif rate < 10 ** 25:          # 1e12 to 1e25: native/volatile vaults
            r = rate / 1e27
        else:
            return None  # likely a liquidity index accumulator, not a rate
        import math
        apy = (math.exp(r * SECS_PER_YEAR) - 1.0) * 100.0
        return apy if apy < 100_000.0 else None  # sanity cap
    except (OverflowError, ZeroDivisionError):
        return None

def fmt_pct(val: Optional[float], decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}%"

def fmt_number(val: Optional[float]) -> str:
    """Format a dollar/token amount: $1.2M, $800K, $1,234."""
    if val is None:
        return "N/A"
    if val >= 1_000_000:
        return f"${val/1_000_000:.2f}M"
    if val >= 1_000:
        return f"${val/1_000:.1f}K"
    return f"${val:.2f}"

def fmt_cap(cap: Optional[float]) -> str:
    if cap is None:
        return "N/A"
    if cap == 0:
        return "None"
    return fmt_number(cap)


# ── DATA CLASS ────────────────────────────────────────────────────────────────

@dataclass
class MarketData:
    cluster: str
    symbol: str
    address: str
    decimals: int = 18
    supply_apy: Optional[float] = None
    borrow_apy: Optional[float] = None
    tvl: Optional[float] = None
    borrows: Optional[float] = None
    utilization: Optional[float] = None
    supply_cap: Optional[float] = None   # 0 = uncapped
    borrow_cap: Optional[float] = None   # 0 = uncapped
    available: Optional[float] = None
    error: Optional[str] = None

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


# ── FETCHERS ──────────────────────────────────────────────────────────────────

def fetch_pooled_markets(client: JsonRpcClient) -> list[MarketData]:
    results = []
    # Step 1: get list of all reserves
    raw = client.eth_call(POOLED_DATA_PROVIDER, SEL["getAllReservesTokens"])
    tokens = decode_token_array(raw)
    if not tokens:
        print("[warn] Pooled Markets: getAllReservesTokens returned empty", file=sys.stderr)
        return results

    for symbol, token_addr in tokens:
        m = MarketData(cluster="Pooled", symbol=symbol, address=token_addr)
        try:
            addr_arg = encode_address(token_addr)

            # getReserveData → word layout (12 words total):
            # [0]=configuration [1]=liquidityIndex [2]=currentLiquidityRate
            # [3]=variableBorrowIndex [4]=currentVariableBorrowRate
            # [5]=currentStableBorrowRate [6]=lastUpdateTimestamp [7]=id
            # [8]=hyToken [9]=stableDebt [10]=variableDebt [11]=IRM
            # NOTE: ProtocolDataProvider.getReserveData returns different layout:
            # [0]=unbacked [1]=accruedToTreasuryScaled [2]=totalAToken
            # [3]=totalStableDebt [4]=totalVariableDebt [5]=liquidityRate
            # [6]=variableBorrowRate [7]=stableBorrowRate [8]=avgStableBorrowRate
            # [9]=liquidityIndex [10]=variableBorrowIndex [11]=lastUpdateTimestamp
            reserve_raw = client.eth_call(
                POOLED_DATA_PROVIDER, SEL["getReserveData"] + addr_arg
            )
            supply_rate_ray = decode_uint256(reserve_raw, 5)
            borrow_rate_ray = decode_uint256(reserve_raw, 6)
            total_atoken    = decode_uint256(reserve_raw, 2)
            total_var_debt  = decode_uint256(reserve_raw, 4)

            # getReserveConfigurationData → [decimals, ltv, liqThreshold, liqBonus, reserveFactor, ...]
            config_raw = client.eth_call(
                POOLED_DATA_PROVIDER, SEL["getReserveConfigurationData"] + addr_arg
            )
            dec = decode_uint256(config_raw, 0) or 18

            # getReserveCaps → [supplyCap, borrowCap] in whole token units (0=uncapped)
            caps_raw = client.eth_call(
                POOLED_DATA_PROVIDER, SEL["getReserveCaps"] + addr_arg
            )
            supply_cap_tokens = decode_uint256(caps_raw, 0)
            borrow_cap_tokens = decode_uint256(caps_raw, 1)

            scale = 10 ** dec
            tvl     = total_atoken / scale if total_atoken is not None else None
            borrows = total_var_debt / scale if total_var_debt is not None else None
            avail   = max(0.0, tvl - borrows) if (tvl is not None and borrows is not None) else None

            util = None
            if tvl and borrows is not None and tvl > 0:
                util = borrows / tvl * 100.0

            m.decimals    = int(dec)
            m.supply_apy  = ray_to_apy_pct(supply_rate_ray)
            m.borrow_apy  = ray_to_apy_pct(borrow_rate_ray)
            m.tvl         = tvl
            m.borrows     = borrows
            m.utilization = util
            m.supply_cap  = float(supply_cap_tokens) if supply_cap_tokens is not None else None
            m.borrow_cap  = float(borrow_cap_tokens) if borrow_cap_tokens is not None else None
            m.available   = avail

        except Exception as exc:
            m.error = str(exc)

        results.append(m)
    return results


def fetch_euler_cluster(
    client: JsonRpcClient,
    cluster_name: str,
    vaults: dict[str, str],
) -> list[MarketData]:
    results = []
    for symbol, vault_addr in vaults.items():
        m = MarketData(cluster=cluster_name, symbol=symbol, address=vault_addr)
        try:
            # Fetch all needed values
            assets_raw  = client.eth_call(vault_addr, SEL["totalAssets"])
            borrows_raw = client.eth_call(vault_addr, SEL["totalBorrows"])
            cash_raw    = client.eth_call(vault_addr, SEL["cash"])
            rate_raw    = client.eth_call(vault_addr, SEL["interestRate"])
            dec_raw     = client.eth_call(vault_addr, SEL["decimals"])
            fee_raw     = client.eth_call(vault_addr, SEL["reserveFee"])

            dec         = int(decode_uint256(dec_raw, 0) or 18)
            reserve_fee = int(decode_uint256(fee_raw, 0) or 1000)  # BPS, default 10%
            scale       = 10 ** dec

            total_assets  = decode_uint256(assets_raw, 0)
            total_borrows = decode_uint256(borrows_raw, 0)
            cash_val      = decode_uint256(cash_raw, 0)
            rate_val      = decode_uint256(rate_raw, 0)

            tvl     = total_assets  / scale if total_assets  is not None else None
            borrows = total_borrows / scale if total_borrows is not None else None
            avail   = cash_val      / scale if cash_val      is not None else None

            util = None
            if tvl and borrows is not None and tvl > 0:
                util = borrows / tvl * 100.0

            borrow_apy = euler_rate_to_apy_pct(rate_val)
            supply_apy = None
            if borrow_apy is not None and util is not None:
                supply_apy = borrow_apy * (util / 100.0) * (1.0 - reserve_fee / 10_000.0)

            m.decimals    = dec
            m.supply_apy  = supply_apy
            m.borrow_apy  = borrow_apy
            m.tvl         = tvl
            m.borrows     = borrows
            m.utilization = util
            m.available   = avail

        except Exception as exc:
            m.error = str(exc)

        results.append(m)
    return results


def fetch_earn_vaults(client: JsonRpcClient) -> list[MarketData]:
    results = []
    for symbol, vault_addr in EARN_VAULTS.items():
        m = MarketData(cluster="Earn", symbol=symbol, address=vault_addr)
        try:
            assets_raw = client.eth_call(vault_addr, SEL["totalAssets"])
            dec_raw    = client.eth_call(vault_addr, SEL["decimals"])

            dec   = int(decode_uint256(dec_raw, 0) or 18)
            scale = 10 ** dec
            total = decode_uint256(assets_raw, 0)

            m.decimals = dec
            m.tvl      = total / scale if total is not None else None

        except Exception as exc:
            m.error = str(exc)

        results.append(m)
    return results


def fetch_user_positions(client: JsonRpcClient, user_addr: str) -> dict:
    result = {"pooled": {}, "euler_vaults": {}}
    addr_arg = encode_address(user_addr)

    # Aave: overall account data
    try:
        raw = client.eth_call(AAVE_POOL, SEL["getUserAccountData"] + addr_arg)
        collateral = decode_uint256(raw, 0)
        debt       = decode_uint256(raw, 1)
        avail_b    = decode_uint256(raw, 2)
        hf         = decode_uint256(raw, 5)
        result["pooled"]["summary"] = {
            "total_collateral_usd": collateral / 1e8 if collateral else 0,
            "total_debt_usd":       debt / 1e8 if debt else 0,
            "available_borrows_usd": avail_b / 1e8 if avail_b else 0,
            "health_factor":        hf / 1e18 if hf else None,
        }
    except Exception as exc:
        result["pooled"]["error"] = str(exc)

    # Euler vaults: balance per vault
    all_vaults = {**PRIME_VAULTS, **YIELD_VAULTS, **SCALE_VAULTS, **EARN_VAULTS}
    for sym, vault_addr in all_vaults.items():
        try:
            bal_raw = client.eth_call(vault_addr, SEL["balanceOf"] + addr_arg)
            max_raw = client.eth_call(vault_addr, SEL["maxWithdraw"] + addr_arg)
            dec_raw = client.eth_call(vault_addr, SEL["decimals"])
            dec     = int(decode_uint256(dec_raw, 0) or 18)
            scale   = 10 ** dec
            bal     = decode_uint256(bal_raw, 0)
            mx      = decode_uint256(max_raw, 0)
            if bal:
                result["euler_vaults"][sym] = {
                    "address":      vault_addr,
                    "shares":       bal / scale,
                    "max_withdraw": mx / scale if mx else 0,
                }
        except Exception:
            pass

    return result


# ── FORMATTERS ────────────────────────────────────────────────────────────────

_COL_WIDTHS = {
    "asset":       9,
    "supply_apy": 11,
    "borrow_apy": 11,
    "tvl":        10,
    "borrows":    10,
    "util":        7,
    "supply_cap": 11,
    "borrow_cap": 11,
    "available":  11,
}

def _row(vals: list[str], widths: list[int]) -> str:
    return "  ".join(v.ljust(w) for v, w in zip(vals, widths))

def print_table(markets: list[MarketData], show_caps: bool = False) -> None:
    if not markets:
        return
    cluster = markets[0].cluster
    print(f"\n{'='*70}")
    print(f"  {cluster}")
    print(f"{'='*70}")

    if show_caps:
        hdrs = ["Asset", "Supply APY", "Borrow APY", "TVL", "Borrows",
                "Util%", "SupplyCap", "BorrowCap", "Available"]
        widths = [_COL_WIDTHS[k] for k in
                  ["asset","supply_apy","borrow_apy","tvl","borrows",
                   "util","supply_cap","borrow_cap","available"]]
    else:
        hdrs = ["Asset", "Supply APY", "Borrow APY", "TVL", "Borrows", "Util%", "Available"]
        widths = [_COL_WIDTHS[k] for k in
                  ["asset","supply_apy","borrow_apy","tvl","borrows","util","available"]]

    print(_row(hdrs, widths))
    print(_row(["-"*w for w in widths], widths))

    for m in markets:
        if m.error:
            vals = [m.symbol] + ["ERR"] * (len(hdrs) - 1)
            print(_row(vals, widths))
            print(f"    └─ {m.error[:80]}", file=sys.stderr)
            continue

        if show_caps:
            vals = [
                m.symbol,
                fmt_pct(m.supply_apy),
                fmt_pct(m.borrow_apy),
                fmt_number(m.tvl),
                fmt_number(m.borrows),
                fmt_pct(m.utilization, 1),
                fmt_cap(m.supply_cap),
                fmt_cap(m.borrow_cap),
                fmt_number(m.available),
            ]
        else:
            vals = [
                m.symbol,
                fmt_pct(m.supply_apy),
                fmt_pct(m.borrow_apy),
                fmt_number(m.tvl),
                fmt_number(m.borrows),
                fmt_pct(m.utilization, 1),
                fmt_number(m.available),
            ]
        print(_row(vals, widths))


def print_earn_table(markets: list[MarketData]) -> None:
    if not markets:
        return
    print(f"\n{'='*70}")
    print("  Earn Vaults  (APY managed by curator — check app for current yield)")
    print(f"{'='*70}")
    hdrs   = ["Vault",    "TVL"]
    widths = [14,          12]
    print(_row(hdrs, widths))
    print(_row(["-"*w for w in widths], widths))
    for m in markets:
        if m.error:
            print(_row([m.symbol, "ERR"], widths))
        else:
            print(_row([m.symbol, fmt_number(m.tvl)], widths))


def print_user_positions(positions: dict) -> None:
    print(f"\n{'='*70}")
    print("  Your Positions")
    print(f"{'='*70}")
    summary = positions.get("pooled", {}).get("summary", {})
    if summary:
        hf = summary.get("health_factor")
        hf_str = f"{hf:.3f}" if hf else "N/A"
        print(f"  Pooled Markets:  collateral=${summary['total_collateral_usd']:.2f}  "
              f"debt=${summary['total_debt_usd']:.2f}  HF={hf_str}")
    euler = positions.get("euler_vaults", {})
    if euler:
        print("  Euler Vaults:")
        for sym, data in euler.items():
            print(f"    {sym:<10}  shares={data['shares']:.4f}  "
                  f"max_withdraw={data['max_withdraw']:.4f}")


def output_json(
    all_markets: dict[str, list[MarketData]],
    user_positions: Optional[dict],
) -> None:
    out: dict = {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for cluster, markets in all_markets.items():
        out[cluster] = [m.as_dict() for m in markets]
    if user_positions:
        out["user_positions"] = user_positions
    print(json.dumps(out, indent=2))


# ── MAIN ──────────────────────────────────────────────────────────────────────

CLUSTER_CHOICES = ("pooled", "prime", "yield", "scale", "earn", "all")

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch live HypurrFi market rates (HyperEVM).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--market",
        choices=CLUSTER_CHOICES,
        default="all",
        help="Which cluster to query (default: all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output machine-readable JSON",
    )
    parser.add_argument(
        "--address",
        metavar="0x...",
        help="Show positions for a wallet address",
    )
    parser.add_argument(
        "--rpc",
        default=DEFAULT_RPC,
        help=f"RPC endpoint (default: {DEFAULT_RPC})",
    )
    args = parser.parse_args()

    client = JsonRpcClient(args.rpc)
    market = args.market
    all_markets: dict[str, list[MarketData]] = {}

    if market in ("pooled", "all"):
        all_markets["Pooled"] = fetch_pooled_markets(client)

    if market in ("prime", "all"):
        all_markets["Prime"] = fetch_euler_cluster(client, "Prime", PRIME_VAULTS)

    if market in ("yield", "all"):
        all_markets["Yield"] = fetch_euler_cluster(client, "Yield", YIELD_VAULTS)

    if market in ("scale", "all"):
        all_markets["Scale"] = fetch_euler_cluster(client, "Scale", SCALE_VAULTS)

    if market in ("earn", "all"):
        all_markets["Earn"] = fetch_earn_vaults(client)

    user_positions = None
    if args.address:
        user_positions = fetch_user_positions(client, args.address)

    if not all_markets:
        print("No data fetched.", file=sys.stderr)
        return 1

    if args.as_json:
        output_json(all_markets, user_positions)
        return 0

    # Print timestamp header
    print(f"\nHypurrFi Market Rates  —  {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print(f"RPC: {args.rpc}")

    for cluster_name, markets in all_markets.items():
        if cluster_name == "Earn":
            print_earn_table(markets)
        else:
            print_table(markets, show_caps=(cluster_name == "Pooled"))

    if user_positions:
        print_user_positions(user_positions)

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
