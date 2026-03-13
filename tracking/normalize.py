"""Normalization utilities.

Single source of truth for:
- symbol parsing
- quote-aware keys

v3 requirement: everything becomes (venue, inst_id) + derived fields.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedInstrument:
    venue: str
    inst_id: str
    raw_symbol: str
    base: str
    quote: str
    contract_type: str  # 'SPOT' | 'PERP'

    @property
    def symbol_key(self) -> str:
        return f"{self.base}:{self.quote}"

    @property
    def symbol_base(self) -> str:
        return self.base


def parse_okx_inst_id(inst_id: str, inst_type: str) -> NormalizedInstrument:
    """Parse OKX instId into normalized instrument fields.

    Examples:
    - SPOT: BTC-USDT
    - PERP (SWAP): BTC-USDT-SWAP

    We treat OKX native instId as inst_id (unique within venue).
    """
    if inst_type == "SPOT":
        parts = inst_id.split("-")
        if len(parts) != 2:
            raise ValueError(f"unexpected OKX SPOT instId: {inst_id}")
        base, quote = parts
        return NormalizedInstrument(
            venue="okx",
            inst_id=inst_id,
            raw_symbol=inst_id,
            base=base,
            quote=quote,
            contract_type="SPOT",
        )

    if inst_type == "SWAP":
        parts = inst_id.split("-")
        if len(parts) < 3 or parts[-1] != "SWAP":
            raise ValueError(f"unexpected OKX SWAP instId: {inst_id}")
        base = parts[0]
        quote = parts[1]
        return NormalizedInstrument(
            venue="okx",
            inst_id=inst_id,
            raw_symbol=inst_id,
            base=base,
            quote=quote,
            contract_type="PERP",
        )

    raise ValueError(f"unsupported OKX instType: {inst_type}")
