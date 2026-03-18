"""Tests for wallet_label in registry."""
import unittest


class TestRegistryWalletLabel(unittest.TestCase):
    def test_leg_config_default_wallet_label(self):
        from tracking.position_manager.registry import LegConfig
        leg = LegConfig(leg_id="l1", venue="hyperliquid", inst_id="BTC", side="LONG", qty=1.0)
        self.assertIsNone(leg.wallet_label)

    def test_leg_config_with_wallet_label(self):
        from tracking.position_manager.registry import LegConfig
        leg = LegConfig(leg_id="l1", venue="hyperliquid", inst_id="BTC", side="LONG", qty=1.0, wallet_label="alt")
        self.assertEqual(leg.wallet_label, "alt")

    def test_parse_position_reads_wallet_label(self):
        from tracking.position_manager.registry import parse_position
        data = {
            "position_id": "p1", "strategy_type": "SPOT_PERP",
            "base": "BTC", "status": "OPEN",
            "legs": [{"leg_id": "l1", "venue": "hyperliquid", "inst_id": "BTC", "side": "LONG", "qty": 1.0, "wallet_label": "alt"}],
        }
        pos = parse_position(data)
        self.assertEqual(pos.legs[0].wallet_label, "alt")

    def test_parse_position_no_wallet_label(self):
        from tracking.position_manager.registry import parse_position
        data = {
            "position_id": "p1", "strategy_type": "SPOT_PERP",
            "base": "BTC", "status": "OPEN",
            "legs": [{"leg_id": "l1", "venue": "hyperliquid", "inst_id": "BTC", "side": "LONG", "qty": 1.0}],
        }
        pos = parse_position(data)
        self.assertIsNone(pos.legs[0].wallet_label)


if __name__ == "__main__":
    unittest.main()
