#!/usr/bin/env python3
"""Morpho Protocol live market data — Felix and all HyperEVM markets.

Felix = curated set of 21 markets + 6 MetaMorpho vaults on HyperEVM (chain 999).
Morpho = all markets deployed on HyperEVM via Morpho Blue.

Usage:
    python3 morpho_rates.py                     # Felix markets + vaults (default)
    python3 morpho_rates.py --market markets    # Felix markets only
    python3 morpho_rates.py --market vaults     # Felix MetaMorpho vaults only
    python3 morpho_rates.py --market morpho     # all Morpho markets on HyperEVM
    python3 morpho_rates.py --market all        # felix + vaults + all morpho
    python3 morpho_rates.py --json              # JSON output
    python3 morpho_rates.py --address 0x...     # include user positions
    python3 morpho_rates.py --chain 999         # override chain ID
"""

import json
import sys
import argparse
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime, timezone

GRAPHQL_URL = "https://api.morpho.org/graphql"
DEFAULT_CHAIN_ID = 999  # HyperEVM

# Felix-curated markets (21 total). Collateral → Loan notation.
FELIX_MARKETS: dict[str, str] = {
    "UETH/USDT0":    "0xf9f0473b23ebeb82c83078f0f0f77f27ac534c9fb227cb4366e6057b6163ffbf",
    "UETH/USDhl":    "0xb5b215bd2771f5ed73125bf6a02e7b743fadc423dfbb095ad59df047c50d3e81",
    "kHYPE/HYPE":    "0x64e7db7f042812d4335947a7cdf6af1093d29478aff5f1ccd93cc67f8aadfddc",
    "kHYPE/USDhl":   "0xc0a3063a0a7755b7d58642e9a6d3be1c05bc974665ef7d3b158784348d4e17c5",
    "kHYPE/USDT0":   "0x78f6b57d825ef01a5dc496ad1f426a6375c685047d07a30cd07ac5107ffc7976",
    "WHYPE/USDe":    "0x292f0a3ddfb642fbaadf258ebcccf9e4b0048a9dc5af93036288502bde1a71b1",
    "WHYPE/USDT0":   "0xace279b5c6eff0a1ce7287249369fa6f4d3d32225e1629b04ef308e0eb568fb0",
    "WHYPE/USDhl":   "0x96c7abf76aed53d50b2cc84e2ed17846e0d1c4cc28236d95b6eb3b12dcc86909",
    "UBTC/USDe":     "0x5fe3ac84f3a2c4e3102c3e6e9accb1ec90c30f6ee87ab1fcafc197b8addeb94c",
    "UBTC/USDT0":    "0x707dddc200e95dc984feb185abf1321cabec8486dca5a9a96fb5202184106e54",
    "UBTC/USDhl":    "0x87272614b7a2022c31ddd7bba8eb21d5ab40a6bcbea671264d59dc732053721d",
    "wstHYPE/HYPE":  "0xbcae0d8e381f600b2919194434a0733899697a4c3b6715a5fa75acf8b84bd755",
    "wstHYPE/USDT0": "0xb39e45107152f02502c001a46e2d3513f429d2363323cdaffbc55a951a69b998",
    "wstHYPE/USDhl": "0x1f79fe1822f6bfe7a70f8e7e5e768efd0c3f10db52af97c2f14e4b71e3130e70",
    "hwHLP/USDhl":   "0xe500760b79e397869927a5275d64987325faae43326daf6be5a560184e30a521",
    "hwHLP/USDT0":   "0x86d7bc359391486de8cd1204da45c53d6ada60ab9764450dc691e1775b2e8d69",
    "wHLP/USDhl":    "0x920244a8682a53b17fe15597b63abdaa3aecec44e070379c5e43897fb9f42a2b",
    "wHLP/USDT0":    "0xd4fd53f612eaf411a1acea053cfa28cbfeea683273c4133bf115b47a20130305",
    "kHYPE-PT/HYPE": "0x1df0d0ebcdc52069692452cb9a3e5cf6c017b237378141eaf08a05ce17205ed6",
    "kHYPE-PT/USDT0":"0x888679b2af61343a4c7c0da0639fc5ca5fc5727e246371c4425e4d634c09e1f6",
    "kHYPE-PT/USDhl":"0xe0a1de770a9a72a083087fe1745c998426aaea984ddf155ea3d5fbba5b759713",
    "kHYPE-PT/USDC": "0xcd9898604b9b658fc3295f86d4cd7f02fa3a6b0a573879f1db9b83369f4951fb",
}

# Felix MetaMorpho lending vaults (18 total, across 4 curators).
# Depositors supply here; curator routes funds into Felix/Morpho markets.
FELIX_VAULT_ADDRS = [
    # Felix-curated
    "0x835febf893c6dddee5cf762b0f8e31c5b06938ab",   # Felix USDe
    "0xfc5126377f0efc0041c0969ef9ba903ce67d151e",   # Felix USDT0
    "0x9896a8605763106e57A51aa0a97Fe8099E806bb3",   # Felix USDT0 (Frontier)
    "0x9c59a9389D8f72DE2CdAf1126F36EA4790E2275e",   # Felix USDhl
    "0x66c71204B70aE27BE6dC3eb41F9aF5868E68fDb6",   # Felix USDhl (Frontier)
    "0x2900ABd73631b2f60747e687095537B673c06A76",   # Felix HYPE
    "0x8A862fD6c12f9ad34C9c2ff45AB2b6712e8CEa27",   # Felix USDC
    "0x808F72b6Ff632fba005C88b49C2a76AB01CAB545",   # Felix USDC (Frontier)
    "0x207ccaE51Ad2E1C240C4Ab4c94b670D438d2201C",   # Felix USDH
    "0x274f854b2042DB1aA4d6C6E45af73588BEd4Fc9D",   # Felix USDH (Frontier)
    # Gauntlet
    "0x08C00F8279dFF5B0CB5a04d349E7d79708Ceadf3",   # Gauntlet USDC
    "0x53A333e51E96FE288bC9aDd7cdC4B1EAD2CD2FfA",   # Gauntlet USDT0
    "0x264a06Fd7A7C9E0Bfe75163b475E2A3cc1856578",   # Gauntlet WHYPE
    # Hyperithm
    "0xF0A23671A810995B04A0f3eD08be86797B608D78",   # Hyperithm USDC
    "0xe5ADd96840F0B908ddeB3Bd144C0283Ac5ca7cA0",   # Hyperithm USDT0
    "0x92B518e1cD76dD70D3E20624AEdd7D107F332Cff",   # Hyperithm HYPE
    # MEV Capital
    "0x3Bcc0a5a66bB5BdCEEf5dd8a659a4eC75F3834d8",   # MEV Capital USDT0
    "0xd19e3d00f8547f7d108abFD4bbb015486437B487",   # MEV Capital HYPE
]


# ── GraphQL queries ────────────────────────────────────────────────────────────

_MARKET_FIELDS = """
  marketId
  loanAsset { symbol decimals }
  collateralAsset { symbol decimals }
  state { supplyApy borrowApy utilization supplyAssets borrowAssets liquidityAssets }
  lltv
"""

MARKETS_BY_IDS_Q = """
query Markets($chainId: Int!, $ids: [String!]) {
  markets(where: { chainId_in: [$chainId], uniqueKey_in: $ids }, first: 100) {
    items {""" + _MARKET_FIELDS + """    }
  }
}
"""

ALL_MARKETS_Q = """
query AllMarkets($chainId: Int!, $skip: Int!) {
  markets(
    where: { chainId_in: [$chainId] }
    first: 100 skip: $skip
    orderBy: SupplyAssets orderDirection: Desc
  ) {
    items {""" + _MARKET_FIELDS + """    }
    pageInfo { countTotal }
  }
}
"""

VAULTS_Q = """
query Vaults($chainId: Int!, $addrs: [String!]) {
  vaults(where: { chainId_in: [$chainId], address_in: $addrs }, first: 20) {
    items {
      address name
      asset { symbol decimals }
      state { totalAssets apy }
    }
  }
}
"""

USER_POSITIONS_Q = """
query UserPos($chainId: Int!, $addr: String!) {
  marketPositions(where: { chainId_in: [$chainId], userAddress_in: [$addr] }) {
    items {
      market {
        marketId
        loanAsset { symbol decimals }
        collateralAsset { symbol decimals }
      }
      supplyAssets borrowAssets collateral
    }
  }
  vaultPositions(where: { chainId_in: [$chainId], userAddress_in: [$addr] }) {
    items {
      vault { address name asset { symbol decimals } }
      assets
    }
  }
}
"""


# ── data types ─────────────────────────────────────────────────────────────────

@dataclass
class MarketData:
    label: str
    market_id: Optional[str] = None
    collateral: Optional[str] = None
    loan: Optional[str] = None
    supply_apy_pct: Optional[float] = None
    borrow_apy_pct: Optional[float] = None
    tvl: Optional[float] = None       # loan token units (normalized)
    borrows: Optional[float] = None   # loan token units
    available: Optional[float] = None # loan token units
    util_pct: Optional[float] = None
    lltv_pct: Optional[float] = None
    loan_decimals: Optional[int] = None
    is_vault: bool = False
    vault_apy_pct: Optional[float] = None
    asset_decimals: Optional[int] = None
    error: Optional[str] = None


# ── GraphQL client ─────────────────────────────────────────────────────────────

class GraphQLClient:
    def __init__(self, url: str = GRAPHQL_URL):
        self.url = url

    def query(self, gql: str, variables: Optional[dict] = None) -> dict:
        payload = json.dumps({"query": gql, "variables": variables or {}}).encode()
        req = urllib.request.Request(
            self.url, data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        last_err = None
        for _ in range(2):
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    result = json.loads(resp.read())
                    if "errors" in result:
                        raise RuntimeError(result["errors"][0]["message"])
                    return result.get("data", {})
            except RuntimeError:
                raise
            except Exception as e:
                last_err = e
        raise RuntimeError(f"GraphQL request failed: {last_err}") from last_err


# ── parsers ────────────────────────────────────────────────────────────────────

def _pct(v) -> Optional[float]:
    return None if v is None else round(float(v) * 100, 4)

def _assets(raw, dec: int) -> Optional[float]:
    return None if raw is None else int(str(raw)) / (10 ** dec)

def _lltv(raw) -> Optional[float]:
    return None if raw is None else round(int(str(raw)) / 1e16, 2)

def _util(v) -> Optional[float]:
    return None if v is None else round(float(v) * 100, 2)

def _market_from_item(label: str, item: dict) -> MarketData:
    state = item.get("state") or {}
    loan = item.get("loanAsset") or {}
    coll = item.get("collateralAsset") or {}
    dec = loan.get("decimals", 18)
    return MarketData(
        label=label,
        market_id=item.get("marketId"),
        collateral=coll.get("symbol"),
        loan=loan.get("symbol"),
        supply_apy_pct=_pct(state.get("supplyApy")),
        borrow_apy_pct=_pct(state.get("borrowApy")),
        tvl=_assets(state.get("supplyAssets"), dec),
        borrows=_assets(state.get("borrowAssets"), dec),
        available=_assets(state.get("liquidityAssets"), dec),
        util_pct=_util(state.get("utilization")),
        lltv_pct=_lltv(item.get("lltv")),
        loan_decimals=dec,
    )


# ── fetchers ───────────────────────────────────────────────────────────────────

def fetch_felix_markets(gql: GraphQLClient, chain_id: int) -> list[MarketData]:
    ids = list(FELIX_MARKETS.values())
    data = gql.query(MARKETS_BY_IDS_Q, {"chainId": chain_id, "ids": ids})
    items = data.get("markets", {}).get("items", [])
    id_to_label = {v.lower(): k for k, v in FELIX_MARKETS.items()}
    results: list[MarketData] = []
    found: set[str] = set()
    for item in items:
        mid = (item.get("marketId") or "").lower()
        label = id_to_label.get(mid, f"{mid[:8]}...")
        results.append(_market_from_item(label, item))
        found.add(mid)
    for label, mid in FELIX_MARKETS.items():
        if mid.lower() not in found:
            results.append(MarketData(label=label, market_id=mid, error="not returned by API"))
    return results


def fetch_all_morpho_markets(gql: GraphQLClient, chain_id: int) -> list[MarketData]:
    all_items: list[dict] = []
    skip = 0
    while True:
        data = gql.query(ALL_MARKETS_Q, {"chainId": chain_id, "skip": skip})
        mkt = data.get("markets", {})
        items = mkt.get("items", [])
        all_items.extend(items)
        total = mkt.get("pageInfo", {}).get("countTotal", 0)
        skip += len(items)
        if not items or skip >= total:
            break
    results: list[MarketData] = []
    for item in all_items:
        loan = (item.get("loanAsset") or {}).get("symbol", "?")
        coll = (item.get("collateralAsset") or {}).get("symbol", "?")
        results.append(_market_from_item(f"{coll}/{loan}", item))
    return results


def fetch_felix_vaults(gql: GraphQLClient, chain_id: int) -> list[MarketData]:
    data = gql.query(VAULTS_Q, {"chainId": chain_id, "addrs": FELIX_VAULT_ADDRS})
    items = data.get("vaults", {}).get("items", [])
    results: list[MarketData] = []
    for item in items:
        state = item.get("state") or {}
        asset = item.get("asset") or {}
        dec = asset.get("decimals", 18)
        tvl = _assets(state.get("totalAssets"), dec)
        results.append(MarketData(
            label=item.get("name", "?"),
            market_id=item.get("address"),
            loan=asset.get("symbol"),
            tvl=tvl,
            asset_decimals=dec,
            is_vault=True,
            vault_apy_pct=_pct(state.get("apy")),
        ))
    results.sort(key=lambda v: v.tvl if v.tvl is not None else -1, reverse=True)
    return results


def fetch_user_positions(gql: GraphQLClient, chain_id: int, address: str) -> dict:
    return gql.query(USER_POSITIONS_Q, {"chainId": chain_id, "addr": address.lower()})


# ── formatters ─────────────────────────────────────────────────────────────────

def fmt_val(v: Optional[float], dec: int = 18, sym: str = "") -> str:
    if v is None:
        return "N/A"
    suffix = f" {sym}" if sym else ""
    prefix = "$" if dec <= 8 else ""  # stablecoin-like → show as $
    if v >= 1_000_000:
        return f"{prefix}{v/1_000_000:.2f}M{suffix}"
    if v >= 1_000:
        return f"{prefix}{v/1_000:.1f}K{suffix}"
    return f"{prefix}{v:.2f}{suffix}"

def fmt_pct(v: Optional[float]) -> str:
    return "N/A" if v is None else f"{v:.2f}%"


def _print_divider(width: int) -> None:
    print("─" * width)


def print_felix_markets(markets: list[MarketData]) -> None:
    print("\n=== Felix Markets ===")
    hdr = f"{'Market':<18} {'Supply APY':>10} {'Borrow APY':>10} {'TVL':>11} {'Borrows':>11} {'Util%':>7} {'LLTV':>6} {'Available':>11}"
    print(hdr)
    _print_divider(len(hdr))
    for m in markets:
        if m.error:
            print(f"{m.label:<18}  error: {m.error}")
            continue
        dec = m.loan_decimals or 18
        sym = m.loan or ""
        native_sym = sym if dec > 8 else ""
        print(
            f"{m.label:<18}"
            f" {fmt_pct(m.supply_apy_pct):>10}"
            f" {fmt_pct(m.borrow_apy_pct):>10}"
            f" {fmt_val(m.tvl, dec, native_sym):>11}"
            f" {fmt_val(m.borrows, dec, native_sym):>11}"
            f" {fmt_pct(m.util_pct):>7}"
            f" {fmt_pct(m.lltv_pct):>6}"
            f" {fmt_val(m.available, dec, native_sym):>11}"
        )


def print_felix_vaults(vaults: list[MarketData]) -> None:
    print("\n=== Felix Vaults (MetaMorpho) ===")
    hdr = f"{'Vault':<30} {'Asset':<8} {'APY':>8} {'TVL':>14}"
    print(hdr)
    _print_divider(len(hdr))
    for v in vaults:
        dec = v.asset_decimals or 18
        sym = v.loan or ""
        print(
            f"{v.label:<30}"
            f" {sym:<8}"
            f" {fmt_pct(v.vault_apy_pct):>8}"
            f" {fmt_val(v.tvl, dec, sym if dec > 8 else ''):>14}"
        )


def print_all_markets(markets: list[MarketData], title: str = "All Morpho Markets (HyperEVM)") -> None:
    print(f"\n=== {title} ===")
    hdr = f"{'Market':<24} {'Supply APY':>10} {'Borrow APY':>10} {'TVL':>12} {'Util%':>7} {'LLTV':>6}"
    print(hdr)
    _print_divider(len(hdr))
    for m in markets:
        if m.error:
            continue
        dec = m.loan_decimals or 18
        sym = m.loan or ""
        label = m.label[:24] if len(m.label) > 24 else m.label
        print(
            f"{label:<24}"
            f" {fmt_pct(m.supply_apy_pct):>10}"
            f" {fmt_pct(m.borrow_apy_pct):>10}"
            f" {fmt_val(m.tvl, dec, sym if dec > 8 else ''):>12}"
            f" {fmt_pct(m.util_pct):>7}"
            f" {fmt_pct(m.lltv_pct):>6}"
        )


def print_user_positions(positions: dict) -> None:
    mkt_pos = (positions.get("marketPositions") or {}).get("items", [])
    vlt_pos = (positions.get("vaultPositions") or {}).get("items", [])
    if not mkt_pos and not vlt_pos:
        print("\n=== User Positions === (none found)")
        return
    print("\n=== User Positions ===")
    if mkt_pos:
        print("\nMarket Positions:")
        for p in mkt_pos:
            mkt = p.get("market") or {}
            loan = mkt.get("loanAsset") or {}
            coll = mkt.get("collateralAsset") or {}
            ldec = loan.get("decimals", 18)
            cdec = coll.get("decimals", 18)
            sup = _assets(p.get("supplyAssets"), ldec)
            bor = _assets(p.get("borrowAssets"), ldec)
            col = _assets(p.get("collateral"), cdec)
            label = f"{coll.get('symbol', '?')}/{loan.get('symbol', '?')}"
            parts = []
            if sup:
                parts.append(f"supply {fmt_val(sup, ldec, loan.get('symbol', ''))}")
            if bor:
                parts.append(f"borrow {fmt_val(bor, ldec, loan.get('symbol', ''))}")
            if col:
                parts.append(f"collateral {fmt_val(col, cdec, coll.get('symbol', ''))}")
            print(f"  {label}: {', '.join(parts) or 'empty'}")
    if vlt_pos:
        print("\nVault Positions:")
        for p in vlt_pos:
            vlt = p.get("vault") or {}
            asset = vlt.get("asset") or {}
            dec = asset.get("decimals", 18)
            assets = _assets(p.get("assets"), dec)
            sym = asset.get("symbol", "")
            name = vlt.get("name", vlt.get("address", "?"))
            print(f"  {name}: {fmt_val(assets, dec, sym)}")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Morpho/Felix live market data (HyperEVM chain 999)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
market modes:
  (default)   Felix markets + vaults
  markets     Felix 21 markets only
  vaults      Felix 6 MetaMorpho vaults only
  morpho      all Morpho markets on HyperEVM
  all         Felix markets + vaults + all Morpho markets
        """,
    )
    parser.add_argument("--market", choices=["markets", "vaults", "morpho", "all"],
                        help="which markets to show (default: felix markets + vaults)")
    parser.add_argument("--json", action="store_true", dest="json_out", help="JSON output")
    parser.add_argument("--address", metavar="0x...", help="include user positions for address")
    parser.add_argument("--chain", type=int, default=DEFAULT_CHAIN_ID, metavar="ID",
                        help=f"chain ID (default: {DEFAULT_CHAIN_ID})")
    args = parser.parse_args()

    gql = GraphQLClient()
    mode = args.market  # None = default (felix markets + vaults)

    show_felix = mode in (None, "markets", "all")
    show_vaults = mode in (None, "vaults", "all")
    show_morpho = mode in ("morpho", "all")

    felix_markets: list[MarketData] = []
    felix_vaults: list[MarketData] = []
    all_markets: list[MarketData] = []
    user_positions: Optional[dict] = None
    errors: list[str] = []

    if show_felix:
        try:
            felix_markets = fetch_felix_markets(gql, args.chain)
        except Exception as e:
            errors.append(f"Felix markets: {e}")

    if show_vaults:
        try:
            felix_vaults = fetch_felix_vaults(gql, args.chain)
        except Exception as e:
            errors.append(f"Felix vaults: {e}")

    if show_morpho:
        try:
            all_markets = fetch_all_morpho_markets(gql, args.chain)
        except Exception as e:
            errors.append(f"Morpho markets: {e}")

    if args.address:
        try:
            user_positions = fetch_user_positions(gql, args.chain, args.address)
        except Exception as e:
            errors.append(f"User positions: {e}")

    if args.json_out:
        out: dict = {"fetched_at": datetime.now(timezone.utc).isoformat(), "chain_id": args.chain}  # type: ignore
        if felix_markets:
            out["felix_markets"] = [asdict(m) for m in felix_markets]
        if felix_vaults:
            out["felix_vaults"] = [asdict(v) for v in felix_vaults]
        if all_markets:
            felix_ids = {m.market_id for m in felix_markets}
            non_felix = [m for m in all_markets if m.market_id not in felix_ids]
            out["morpho_markets"] = [asdict(m) for m in (all_markets if mode == "morpho" else non_felix)]
        if user_positions:
            out["user_positions"] = user_positions
        if errors:
            out["errors"] = errors
        print(json.dumps(out, indent=2))
        return

    if felix_markets:
        print_felix_markets(felix_markets)

    if felix_vaults:
        print_felix_vaults(felix_vaults)

    if all_markets:
        felix_ids = {m.market_id for m in felix_markets}
        if mode == "all":
            non_felix = [m for m in all_markets if m.market_id not in felix_ids]
            print_all_markets(non_felix, "Other Morpho Markets (HyperEVM)")
        else:
            print_all_markets(all_markets)

    if user_positions:
        print_user_positions(user_positions)

    if errors:
        for e in errors:
            print(f"[error] {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
