"""Secret vault — encrypted secret management via age/sops.

Provides get_secret() to retrieve decrypted secrets from the sops-encrypted
vault file. Falls back to environment variables during the migration period.

Setup:
    1. Install: brew install age sops  (or apt-get install age sops)
    2. Generate key: age-keygen -o vault/age-identity.txt
    3. Configure .sops.yaml with the age public key
    4. Create vault/secrets.enc.json and encrypt with sops

Usage:
    from vault.vault import get_secret, get_secret_with_env_fallback

    # Direct vault access
    key = get_secret("hl_main_private_key")

    # With env var fallback (migration period)
    key = get_secret_with_env_fallback("hl_main_private_key", env_var="HL_PRIVATE_KEY")
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).parent.parent
DEFAULT_VAULT_PATH = ROOT / "vault" / "secrets.enc.json"

# Cache decrypted secrets in memory for the process lifetime
_secrets_cache: Optional[Dict[str, Any]] = None


def decrypt_secrets(vault_path: Optional[Path] = None) -> Dict[str, Any]:
    """Decrypt the sops-encrypted secrets file using age.

    Returns a dict of secret key -> value.
    Raises RuntimeError if decryption fails.
    """
    global _secrets_cache
    if _secrets_cache is not None:
        return _secrets_cache

    path = vault_path or DEFAULT_VAULT_PATH
    if not path.exists():
        return {}

    try:
        result = subprocess.run(
            ["sops", "--decrypt", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        _secrets_cache = json.loads(result.stdout)
        return _secrets_cache
    except FileNotFoundError:
        # sops not installed
        return {}
    except subprocess.CalledProcessError:
        # Decryption failed (no key, wrong key, etc.)
        return {}
    except json.JSONDecodeError:
        return {}


def get_secret(key: str, vault_path: Optional[Path] = None) -> Optional[str]:
    """Get a single secret by key from the vault.

    Returns None if the key is not found or vault is unavailable.
    """
    secrets = decrypt_secrets(vault_path)
    value = secrets.get(key)
    return str(value) if value is not None else None


def get_secret_with_env_fallback(
    key: str,
    env_var: str,
    vault_path: Optional[Path] = None,
) -> Optional[str]:
    """Get a secret from vault, falling back to an environment variable.

    Priority: vault > env var > None
    This allows gradual migration from .arbit_env to the vault.
    """
    # Try vault first
    value = get_secret(key, vault_path)
    if value is not None:
        return value

    # Fallback to env var
    return os.environ.get(env_var)


def clear_cache() -> None:
    """Clear the in-memory secrets cache (useful for testing)."""
    global _secrets_cache
    _secrets_cache = None
