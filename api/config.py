"""API configuration — settings loaded from vault with env fallback."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from functools import lru_cache
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class Settings(BaseModel):
    """Application settings.

    Loaded once at startup. API key comes from vault with env fallback.
    """

    db_path: Path = ROOT / "tracking" / "db" / "arbit_v3.db"
    api_key: str = ""
    cors_origins: list[str] = [
        "http://localhost:3000",           # local Next.js dev
        "https://localhost:3000",
    ]
    # Additional Vercel domains added via HARMONIX_CORS_ORIGINS env var
    # Format: comma-separated URLs


@lru_cache
def get_settings() -> Settings:
    """Build settings, resolving API key from vault then env."""
    # Resolve API key: vault first, then env fallback
    api_key = ""
    try:
        from vault.vault import get_secret_with_env_fallback

        api_key = get_secret_with_env_fallback(
            key="api_key",
            env_var="HARMONIX_API_KEY",
        ) or ""
    except Exception:
        # Vault not available — try pure env
        api_key = os.environ.get("HARMONIX_API_KEY", "")

    # Resolve CORS origins
    cors_origins = Settings().cors_origins.copy()
    extra = os.environ.get("HARMONIX_CORS_ORIGINS", "")
    if extra:
        cors_origins.extend(
            origin.strip() for origin in extra.split(",") if origin.strip()
        )

    # Resolve DB path override
    db_path = Path(os.environ.get("HARMONIX_DB_PATH", str(Settings().db_path)))

    return Settings(
        db_path=db_path,
        api_key=api_key,
        cors_origins=cors_origins,
    )
