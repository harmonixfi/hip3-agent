#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.normalize import parse_okx_inst_id


def main() -> int:
    spot = parse_okx_inst_id("BTC-USDT", "SPOT")
    perp = parse_okx_inst_id("BTC-USDT-SWAP", "SWAP")

    assert spot.inst_id != perp.inst_id
    assert spot.base == "BTC" and spot.quote == "USDT" and spot.contract_type == "SPOT"
    assert perp.base == "BTC" and perp.quote == "USDT" and perp.contract_type == "PERP"

    assert spot.symbol_key == "BTC:USDT"
    assert perp.symbol_key == "BTC:USDT"

    print("OK: OKX v3 normalization tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
