"""
Analytics module for cross-venue arbitrage.

Includes:
- basis: Basis/spread computation
- opportunity_screener: Funding arbitrage opportunity screening
"""

from .basis import BasisEngine
from .opportunity_screener import OpportunityScreener, Opportunity

__all__ = ['BasisEngine', 'OpportunityScreener', 'Opportunity']
