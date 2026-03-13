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

For OKX spot-perp basis matching, use get_quote_aware_key() instead.
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


def parse_okx_inst(inst_id: str) -> Tuple[str, str, str]:
    """
    Parse an OKX instrument ID into base, quote, and contract kind.

    This function provides detailed parsing for OKX instrument IDs,
    which is needed for quote-aware spot-perp basis matching.

    Args:
        inst_id: OKX instrument ID (e.g., 'BTC-USDT-SWAP', 'BTC-USDT', 'ETH-USD-SWAP')

    Returns:
        Tuple of (base_currency, quote_currency, kind)
        where kind is one of: 'PERP', 'SPOT', 'FUTURES', or 'UNKNOWN'

    Examples:
        - 'BTC-USDT-SWAP' -> ('BTC', 'USDT', 'PERP')
        - 'BTC-USDT' -> ('BTC', 'USDT', 'SPOT')
        - 'ETH-USD-SWAP' -> ('ETH', 'USD', 'PERP')
        - 'ETH-USD-240329' -> ('ETH', 'USD', 'FUTURES')
        - 'invalid' -> (None, None, 'UNKNOWN')
    """
    if not inst_id:
        return (None, None, 'UNKNOWN')

    parts = inst_id.split('-')

    if len(parts) < 2:
        return (None, None, 'UNKNOWN')

    base = parts[0].upper()
    quote = parts[1].upper()

    # Determine contract kind from suffixes
    if 'SWAP' in parts:
        kind = 'PERP'
    elif len(parts) == 2:
        # No suffix = SPOT
        kind = 'SPOT'
    elif any(part.isdigit() for part in parts[2:]):
        # Date suffix = FUTURES
        kind = 'FUTURES'
    else:
        kind = 'UNKNOWN'

    return (base, quote, kind)


def get_quote_aware_key(venue: str, raw_symbol: str) -> str:
    """
    Get a quote-aware symbol key for spot-perp matching.

    This returns a base-quote key (e.g., 'BTC-USDT') instead of just the base.
    This is essential for OKX spot-perp basis calculations where spot BTC-USDT
    should only match perp BTC-USDT-SWAP, not BTC-USD-SWAP or BTC-AUD.

    Args:
        venue: Venue identifier
        raw_symbol: Raw symbol from the venue

    Returns:
        Quote-aware key (base-quote) for OKX, base-only for other venues

    Examples:
        - ('okx', 'BTC-USDT-SWAP') -> 'BTC-USDT'
        - ('okx', 'BTC-USDT') -> 'BTC-USDT'
        - ('okx', 'BTC-USD-SWAP') -> 'BTC-USD'
        - ('paradex', 'ETH-USD-PERP') -> 'ETH' (base-only for non-OKX)
        - ('hyperliquid', 'SOL') -> 'SOL' (base-only for non-OKX)

    Note:
        For perp-perp matching across exchanges, use normalize_symbol() (base-only).
        Use this function only for spot-perp matching within the same exchange (OKX).
    """
    venue = venue.lower()

    if venue == 'okx':
        base, quote, kind = parse_okx_inst(raw_symbol)
        if base and quote:
            return f"{base}-{quote}"

    # For non-OKX venues or if parsing failed, fall back to base-only
    return normalize_symbol(venue, raw_symbol)


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

        # Test OKX-specific functions
        if venue == 'okx':
            base_okx, quote_okx, kind = parse_okx_inst(raw_symbol)
            print(f"OKX Parse: base={base_okx}, quote={quote_okx}, kind={kind}")
            quote_key = get_quote_aware_key(venue, raw_symbol)
            print(f"Quote-aware key: {quote_key}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
