=== Task 1 Fix Checkpoint ===
Timestamp: 2026-03-13T08:57:05Z
Status: DONE

Changes:
1. core_tier_portfolio_construction.py: Added check after candidate processing - returns DEGRADED with warning 'no valid funding rows in csv' when CSV exists but yields no valid candidates
2. test_core_tier_portfolio_construction.py: Added pytest.approx assertion for apr_latest (expected 43.8% for fixture funding_8h_rate=0.0004)
