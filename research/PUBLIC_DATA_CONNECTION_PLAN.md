# Public data connection rollout

## Connected without user API keys

The repository now has automated daily refresh plumbing for:

- BLS labor/inflation series
- U.S. Treasury daily par yield curve
- Federal Reserve G.17 industrial production
- NY Fed SOFR/EFFR reference rates
- Federal Reserve SLOOS lending standards
- OECD U.S. CLI
- World Bank long-history U.S. macro series
- SEC ticker/CIK/exchange mapping
- GDELT rolling 3-month aggregate news coverage
- U.S. Treasury Daily Treasury Statement operating cash / TGA data
- NY Fed repo and reverse-repo operation results
- Federal Reserve-published total assets, reserve balances, IORB and target-range series

The scheduled workflow writes only public/static outputs to `docs/data/` and keeps source failures explicit.

## Connected architecture but still gated

Price history for SPY/QQQ/DIA, headline indices and sector ETFs already has fetch/merge/derived-structure pipelines, but the public GitHub Pages site intentionally blocks publication until the chosen market-data licence explicitly permits public display/static JSON redistribution.

## Alternative path while public-price rights are unresolved

The repository already contains personal/local data tooling. Vendor data that is valid for individual use but not public redistribution should be imported locally rather than committed to `docs/data/`. This keeps the research calculations usable without leaking a key or violating display terms.

## Inputs that may still be worth registering later

- A market-price provider/API plan with explicit public website display rights (highest priority for `market_history.json`).
- BEA API key if direct BEA GDP/PCE/corporate-profit ingestion is desired instead of relying on other official/open macro routes.
- FRED API key only if higher-rate metadata/vintage endpoints are needed; normal no-key official-source coverage does not depend on it.
- A warehouse/BigQuery or bulk-ingest route for deep historical GDELT Event/GKG research beyond the DOC API rolling window.

Do not commit credentials or raw vendor OHLCV whose redistribution rights are unclear.
