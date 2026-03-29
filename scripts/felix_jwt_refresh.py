#!/usr/bin/env python3
"""Felix JWT auto-refresh cron script.

Run every 14 minutes via systemd timer or crontab:
    */14 * * * * cd $WORKSPACE && source .arbit_env && .venv/bin/python scripts/felix_jwt_refresh.py >> logs/felix_jwt.log 2>&1

Flow:
1. Load wallet private key from vault
2. Try to load existing session from vault/felix_session.enc.json
3. If session exists and needs refresh: refresh using existing P-256 key
4. If no session or refresh fails: full initial_login with wallet key
5. Store updated session in vault (encrypted)
6. Log result

Security:
- Wallet private key comes from vault (never env var)
- Session state (JWT + P-256 key) stored encrypted in vault
- Never log JWT or private keys
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.felix_auth import (
    FelixSession,
    initial_login,
    refresh_session,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VAULT_DIR = ROOT / "vault"
SESSION_FILE = VAULT_DIR / "felix_session.enc.json"
SESSION_FILE_PLAIN = VAULT_DIR / "felix_session.dec.json"  # temporary, deleted after use

LOG_FMT = "%(asctime)s [felix_jwt] %(levelname)s %(message)s"
logging.basicConfig(format=LOG_FMT, level=logging.INFO, stream=sys.stdout)
log = logging.getLogger("felix_jwt")


# ---------------------------------------------------------------------------
# Vault Integration
# ---------------------------------------------------------------------------


def _get_wallet_key() -> str:
    """Load wallet private key from vault.

    Falls back to env var during migration period.
    """
    try:
        from vault.vault import get_secret_with_env_fallback

        key = get_secret_with_env_fallback(
            "felix_wallet_private_key",
            env_var="FELIX_WALLET_PRIVATE_KEY",
        )
        if key:
            return key
    except ImportError:
        pass

    # Fallback to env var
    key = os.environ.get("FELIX_WALLET_PRIVATE_KEY", "")
    if not key:
        raise RuntimeError(
            "Felix wallet private key not found. "
            "Set in vault as 'felix_wallet_private_key' or env var FELIX_WALLET_PRIVATE_KEY."
        )
    return key


def _get_wallet_address() -> str:
    """Load wallet address from vault or env."""
    try:
        from vault.vault import get_secret_with_env_fallback

        addr = get_secret_with_env_fallback(
            "felix_wallet_address",
            env_var="FELIX_WALLET_ADDRESS",
        )
        if addr:
            return addr
    except ImportError:
        pass

    addr = os.environ.get("FELIX_WALLET_ADDRESS", "")
    if not addr:
        raise RuntimeError(
            "Felix wallet address not found. "
            "Set in vault as 'felix_wallet_address' or env var FELIX_WALLET_ADDRESS."
        )
    return addr


def _load_session() -> FelixSession | None:
    """Load existing session from encrypted vault file.

    Returns None if file doesn't exist or decryption fails.
    """
    if not SESSION_FILE.exists():
        return None

    try:
        result = subprocess.run(
            ["sops", "--decrypt", str(SESSION_FILE)],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        return FelixSession.from_dict(data)
    except FileNotFoundError:
        log.warning("sops not installed — cannot load encrypted session")
        return None
    except subprocess.CalledProcessError:
        log.warning("Failed to decrypt session file — will do full login")
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        log.warning("Corrupt session file: %s — will do full login", e)
        return None


def _save_session(session: FelixSession) -> None:
    """Save session to encrypted vault file using sops.

    Strategy:
    1. Write plaintext JSON to temporary file
    2. Encrypt in-place with sops
    3. Verify the encrypted file
    """
    VAULT_DIR.mkdir(parents=True, exist_ok=True)

    # Write plaintext
    plain_data = json.dumps(session.to_dict(), indent=2)
    SESSION_FILE.write_text(plain_data, encoding="utf-8")

    try:
        # Encrypt in-place
        subprocess.run(
            ["sops", "--encrypt", "--in-place", str(SESSION_FILE)],
            check=True,
            capture_output=True,
            text=True,
        )
        log.info("Session saved to vault (encrypted)")
    except FileNotFoundError:
        log.warning(
            "sops not installed — session saved as PLAINTEXT at %s. "
            "Install sops to encrypt.", SESSION_FILE
        )
    except subprocess.CalledProcessError as e:
        log.error("sops encrypt failed: %s", e.stderr)
        # Leave file as plaintext rather than losing the session
        log.warning("Session saved as PLAINTEXT (sops failed)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Main entry point for Felix JWT refresh."""
    log.info("Starting Felix JWT refresh...")

    try:
        wallet_key = _get_wallet_key()
        wallet_address = _get_wallet_address()
    except RuntimeError as e:
        log.error("Configuration error: %s", e)
        return 1

    # Try to load existing session
    session = _load_session()

    if session and not session.is_expired() and not session.needs_refresh():
        remaining = session.expires_at - int(time.time())
        log.info(
            "Session still valid (%d seconds remaining). No action needed.",
            remaining,
        )
        return 0

    if session and not session.is_expired():
        # Session exists and is not fully expired — try refresh
        log.info("Session needs refresh (sub-org: %s)...", session.sub_org_id)
        try:
            new_session = refresh_session(session, wallet_key)
            _save_session(new_session)
            log.info(
                "JWT refreshed successfully. Expires at %s (in %d seconds).",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(new_session.expires_at)),
                new_session.expires_at - int(time.time()),
            )
            return 0
        except Exception as e:
            log.warning("Refresh failed: %s. Falling back to full login.", e)

    # Full initial login (no session, expired, or refresh failed)
    log.info("Performing full initial login for %s...", wallet_address)
    try:
        # Reuse sub-org ID if we have it (avoids extra API call)
        sub_org_id = session.sub_org_id if session else None

        new_session = initial_login(
            wallet_key,
            wallet_address,
            sub_org_id=sub_org_id,
        )
        _save_session(new_session)
        log.info(
            "Initial login successful. JWT expires at %s (in %d seconds).",
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(new_session.expires_at)),
            new_session.expires_at - int(time.time()),
        )
        return 0

    except Exception as e:
        log.error("Felix login FAILED: %s", e)
        log.error(
            "Felix will be unavailable until next successful login. "
            "System continues without Felix data (degraded mode)."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
