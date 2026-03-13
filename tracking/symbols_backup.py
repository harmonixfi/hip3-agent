"""
Symbol normalization utilities for cross-venue arbitrage.

Provides canonical symbol normalization for all venues so that
shared symbols can be joined across venues.

Canonical standard:
- Use base asset ticker only (uppercase, 3-5 characters typically)
- Strip quote currency suffixes (USDT, USD, USDC, etc.)
- Strip contract type suffixes (SWAP, PERP, FUTURES, etc.)
- Examples:
  - OKX: 'BTC-USDT-SWAP' -> 'BTC'
  - Paradex: 'BTC-USD-PERP' -> 'BTC'
  - Ethereal: 'BTCUSD' -> 'BTC'
  - Lighter: 'BTC' -> 'BTC'
  - Hyperliquid: 'BTC' -> 'BTC'
"""

import re
from typing import Dict, Optional, Tuple


# ============================================================================
# CONFIGURATION
# ============================================================================

# Canonical symbol format
# - Base asset ticker only (uppercase)
# - 2-5 characters typically (BTC, ETH, SOL, BERA, DOGE, etc.)
# - No suffixes, no special characters


# ============================================================================
# OVERRIDES MAPPING
# ============================================================================

# Manual overrides for edge cases that don't parse correctly
# Format: { (venue, raw_symbol): canonical_symbol }
SYMBOL_OVERRIDES: Dict[Tuple[str, str], str] = {
    # Add special cases here as needed
    # Example: ("okx", "1INCH-USDT-SWAP"): "1INCH",
}


# ============================================================================
# PARSING RULES PER VENUE
# ============================================================================

def _parse_okx_symbol(raw_symbol: str) -> Optional[str]:
    """
    Parse OKX instrument ID to extract base asset.

    OKX format: 'BTC-USDT-SWAP', 'ETH-USDC-SWAP', 'SOL-USDT-SWAP'
    Base is the first component before the first hyphen.

    Args:
        raw_symbol: Raw instrument ID (e.g., 'BTC-USDT-SWAP')

    Returns:
        Base asset (e.g., 'BTC') or None if parsing fails
    """
    if not raw_symbol:
        return None

    # Split on hyphen, take first component
    parts = raw_symbol.split('-')
    if parts and parts[0]:
        return parts[0].upper()

    return None


def _parse_paradex_symbol(raw_symbol: str) -> Optional[str]:
    """
    Parse Paradex market string to extract base asset.

    Paradex format: 'BTC-USD-PERP', 'ETH-USD-PERP'
    Base is the first component before the first hyphen.

    Args:
        raw_symbol: Raw market string (e.g., 'BTC-USD-PERP')

    Returns:
        Base asset (e.g., 'BTC') or None if parsing fails
    """
    if not raw_symbol:
        return None

    # Split on hyphen, take first component
    parts = raw_symbol.split('-')
    if parts and parts[0]:
        return parts[0].upper()

    return None


def _parse_ethereal_symbol(raw_symbol: str) -> Optional[str]:
    """
    Parse Ethereal ticker to extract base asset.

    Ethereal format: 'BTCUSD', 'ETHUSD'
    Base is everything before 'USD' suffix.

    Args:
        raw_symbol: Raw ticker (e.g., 'BTCUSD')

    Returns:
        Base asset (e.g., 'BTC') or None if parsing fails
    """
    if not raw_symbol:
        return None

    # Strip 'USD' suffix if present
    if raw_symbol.upper().endswith('USD'):
        return raw_symbol[:-3].upper()

    # If no USD suffix, assume the whole thing is the base
    return raw_symbol.upper()


def _parse_lighter_symbol(raw_symbol: str) -> Optional[str]:
    """
    Parse Lighter symbol to extract base asset.

    Lighter format: 'BTC', 'ETH', 'SOL' (already base-only)

    Args:
        raw_symbol: Raw symbol (e.g., 'BTC')

    Returns:
        Base asset (e.g., 'BTC') or None if parsing fails
    """
    if not raw_symbol:
        return None

    # Lighter symbols are already base-only
    return raw_symbol.upper()


def _parse_hyperliquid_symbol(raw_symbol: str) -> Optional[str]:
    """
    Parse Hyperliquid symbol to extract base asset.

    Hyperliquid format: 'BTC', 'ETH', 'SOL' (usually base-only)
    But may include suffixes in some cases.

    Args:
        raw_symbol: Raw symbol (e.g., 'BTC')

    Returns:
        Base asset (e.g., 'BTC') or None if parsing fails
    """
    if not raw_symbol:
        return None

    # Strip common suffixes if present
    symbol = raw_symbol.upper()
    suffixes = ['-PERP', '_PERP', '-SWAP', '_SWAP', '-USD', '_USD']
    for suffix in suffixes:
        if symbol.endswith(suffix):
            symbol = symbol[:-len(suffix)]

    return symbol


# Venue-specific parser registry
_VENUE_PARSERS: Dict[str, callable] = {
    'okx': _parse_okx_symbol,
    'paradex': _parse_paradex_symbol,
    'ethereal': _parse_ethereal_symbol,
    'lighter': _parse_lighter_symbol,
    'hyperliquid': _parse_hyperliquid_symbol,
}


# ============================================================================
# MAIN NORMALIZATION FUNCTIONS
# ============================================================================

def normalize_symbol(venue: str, raw_symbol: str) -> str:
    """
    Normalize a venue-specific symbol to canonical form.

    Args:
        venue: Venue identifier ('okx', 'paradex', 'ethereal', 'lighter', 'hyperliquid')
        raw_symbol: Raw instrument ID from the venue

    Returns:
        Canonical symbol (base asset only, uppercase)

    Raises:
        ValueError: If venue is not supported or symbol cannot be normalized
    """
    venue = venue.lower()
    raw_symbol = raw_symbol.strip() if raw_symbol else ""

    # Check for manual overrides first
    override_key = (venue, raw_symbol)
    if override_key in SYMBOL_OVERRIDES:
        return SYMBOL_OVERRIDES[override_key]

    # Get venue-specific parser
    parser = _VENUE_PARSERS.get(venue)
    if not parser:
        raise ValueError(f"Unsupported venue: {venue}")

    # Parse the symbol
    canonical = parser(raw_symbol)

    if not canonical:
        raise ValueError(f"Failed to normalize symbol: {venue}:{raw_symbol}")

    # Validate result (alphanumeric only, 1-20 chars)
    # Note: Some crypto tickers are long (e.g., 1000PEPE, JELLYJELLY, FARTCOIN)
    # Some are single letters (e.g., S, A, F, H, W)
    if not re.match(r'^[A-Z0-9]{1,20}$', canonical):
        raise ValueError(f"Invalid canonical symbol format: {canonical} (from {venue}:{raw_symbol})")

    return canonical


def normalize_instrument_id(venue: str, raw_symbol: str) -> str:
    """
    Get the venue-specific instrument ID (no normalization).

    This is useful for preserving the original venue identifier
    for API calls or inst_id column.

    Args:
        venue: Venue identifier
        raw_symbol: Raw symbol from the venue

    Returns:
        The original raw_symbol (unchanged)
    """
    return raw_symbol.strip() if raw_symbol else ""


def parse_base_quote(venue: str, raw_symbol: str) -> Tuple[str, str]:
    """
    Parse base and quote currencies from a venue-specific symbol.

    Args:
        venue: Venue identifier
        raw_symbol: Raw symbol from the venue

    Returns:
        Tuple of (base_currency, quote_currency)

    Examples:
        - ('okx', 'BTC-USDT-SWAP') -> ('BTC', 'USDT')
        - ('paradex', 'ETH-USD-PERP') -> ('ETH', 'USD')
        - ('ethereal', 'SOLUSD') -> ('SOL', 'USD')
    """
    venue = venue.lower()

    if venue == 'okx':
        parts = raw_symbol.split('-')
        if len(parts) >= 2:
            return (parts[0].upper(), parts[1].upper())
    elif venue == 'paradex':
        parts = raw_symbol.split('-')
        if len(parts) >= 2:
            return (parts[0].upper(), parts[1].upper())
    elif venue == 'ethereal':
        if raw_symbol.upper().endswith('USD'):
            return (raw_symbol[:-3].upper(), 'USD')
    elif venue == 'lighter':
        return (raw_symbol.upper(), 'USD')
    elif venue == 'hyperliquid':
        symbol = raw_symbol.upper()
        suffixes = ['-USD', '_USD']
        for suffix in suffixes:
            if symbol.endswith(suffix):
                return (symbol[:-len(suffix)], 'USD')
        return (symbol, 'USD')

    # Default fallback
    base = normalize_symbol(venue, raw_symbol)
    return (base, 'USD')


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_supported_venues() -> list:
    """Return list of supported venue identifiers."""
    return list(_VENUE_PARSERS.keys())


def is_supported_venue(venue: str) -> bool:
    """Check if a venue is supported for symbol normalization."""
    return venue.lower() in _VENUE_PARSERS


def add_override(venue: str, raw_symbol: str, canonical_symbol: str):
    """
    Add a manual override for a specific symbol.

    Args:
        venue: Venue identifier
        raw_symbol: Raw symbol from the venue
        canonical_symbol: Canonical symbol to use instead of parsing
    """
    SYMBOL_OVERRIDES[(venue.lower(), raw_symbol)] = canonical_symbol.upper()


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

if __name__ == '__main__':
    import sys

    # Simple CLI for testing
    if len(sys.argv) < 3:
        print("Usage: python symbols.py <venue> <raw_symbol>")
        print(f"Supported venues: {', '.join(get_supported_venues())}")
        print("\nExamples:")
        print("  python symbols.py okx BTC-USDT-SWAP")
        print("  python symbols.py paradex BTC-USD-PERP")
        print("  python symbols.py ethereal BTCUSD")
        print("  python symbols.py lighter BTC")
        sys.exit(1)

    venue = sys.argv[1]
    raw_symbol = sys.argv[2]

    try:
        canonical = normalize_symbol(venue, raw_symbol)
        base, quote = parse_base_quote(venue, raw_symbol)
        print(f"Venue: {venue}")
        print(f"Raw symbol: {raw_symbol}")
        print(f"Canonical symbol: {canonical}")
        print(f"Base/Quote: {base}/{quote}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
