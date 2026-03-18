"""Tests for multi-wallet support."""

import json
import os
import unittest


class TestResolveVenueAccounts(unittest.TestCase):
    """Test tracking.position_manager.accounts.resolve_venue_accounts()."""

    def setUp(self):
        for key in list(os.environ):
            if key.endswith("_ACCOUNTS_JSON"):
                del os.environ[key]
        for key in [
            "HYPERLIQUID_ADDRESS", "ETHEREAL_ACCOUNT_ADDRESS",
            "PARADEX_ACCOUNT_ADDRESS", "HYENA_ADDRESS",
            "LIGHTER_L1_ADDRESS",
            "OKX_API_KEY", "OKX_API_SECRET", "OKX_API_PASSPHRASE",
        ]:
            os.environ.pop(key, None)

    def test_accounts_json_present(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["HYPERLIQUID_ACCOUNTS_JSON"] = json.dumps({"main": "0xabc", "alt": "0xdef"})
        result = resolve_venue_accounts("hyperliquid")
        self.assertEqual(result, {"main": "0xabc", "alt": "0xdef"})

    def test_legacy_fallback_hyperliquid(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["HYPERLIQUID_ADDRESS"] = "0xlegacy"
        result = resolve_venue_accounts("hyperliquid")
        self.assertEqual(result, {"main": "0xlegacy"})

    def test_legacy_fallback_hyperliquid_ethereal(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["ETHEREAL_ACCOUNT_ADDRESS"] = "0xeth_fallback"
        result = resolve_venue_accounts("hyperliquid")
        self.assertEqual(result, {"main": "0xeth_fallback"})

    def test_legacy_fallback_paradex(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["PARADEX_ACCOUNT_ADDRESS"] = "0xpdx"
        result = resolve_venue_accounts("paradex")
        self.assertEqual(result, {"main": "0xpdx"})

    def test_no_config_returns_empty(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        result = resolve_venue_accounts("hyperliquid")
        self.assertEqual(result, {})

    def test_accounts_json_overrides_legacy(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["HYPERLIQUID_ADDRESS"] = "0xold"
        os.environ["HYPERLIQUID_ACCOUNTS_JSON"] = json.dumps({"main": "0xnew"})
        result = resolve_venue_accounts("hyperliquid")
        self.assertEqual(result, {"main": "0xnew"})

    def test_legacy_fallback_hyena(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["HYENA_ADDRESS"] = "0xhyena"
        result = resolve_venue_accounts("hyena")
        self.assertEqual(result, {"main": "0xhyena"})

    def test_legacy_fallback_lighter(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["LIGHTER_L1_ADDRESS"] = "0xlighter"
        result = resolve_venue_accounts("lighter")
        self.assertEqual(result, {"main": "0xlighter"})

    def test_legacy_fallback_okx(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["OKX_API_KEY"] = "key123"
        result = resolve_venue_accounts("okx")
        self.assertEqual(result, {"main": "key123"})


if __name__ == "__main__":
    unittest.main()
