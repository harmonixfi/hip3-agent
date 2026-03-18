"""Tests for connector credential overrides."""
import os
import unittest


class TestConnectorOverrides(unittest.TestCase):
    def test_hyperliquid_address_override(self):
        from tracking.connectors.hyperliquid_private import HyperliquidPrivateConnector
        connector = HyperliquidPrivateConnector(address="0xoverride")
        self.assertEqual(connector.address, "0xoverride")

    def test_hyperliquid_env_still_works(self):
        from tracking.connectors.hyperliquid_private import HyperliquidPrivateConnector
        os.environ["HYPERLIQUID_ADDRESS"] = "0xenv"
        try:
            connector = HyperliquidPrivateConnector()
            self.assertEqual(connector.address, "0xenv")
        finally:
            del os.environ["HYPERLIQUID_ADDRESS"]

    def test_hyena_address_override(self):
        from tracking.connectors.hyena_private import HyenaPrivateConnector
        connector = HyenaPrivateConnector(address="0xhyena_override")
        self.assertEqual(connector.address, "0xhyena_override")


if __name__ == "__main__":
    unittest.main()
