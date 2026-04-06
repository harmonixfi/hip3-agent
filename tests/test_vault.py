#!/usr/bin/env python3
"""Tests for vault secret management."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from vault.vault import get_secret, get_secret_with_env_fallback


def test_env_fallback():
    """When vault is not available, falls back to env var."""
    with patch.dict(os.environ, {"TEST_SECRET": "from_env"}):
        result = get_secret_with_env_fallback("test_key", env_var="TEST_SECRET")
        assert result == "from_env"


def test_env_fallback_missing():
    """When both vault and env var are missing, returns None."""
    env = os.environ.copy()
    env.pop("NONEXISTENT_VAR", None)
    with patch.dict(os.environ, env, clear=True):
        result = get_secret_with_env_fallback("test_key", env_var="NONEXISTENT_VAR")
        assert result is None


def main() -> int:
    test_env_fallback()
    print("PASS: test_env_fallback")
    test_env_fallback_missing()
    print("PASS: test_env_fallback_missing")
    print("\nAll vault tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
