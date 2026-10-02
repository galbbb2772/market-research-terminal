# Published data directory

Public/static outputs in this directory are split by rights and purpose:

- `official_sources.json`: generated daily from no-key official/open sources (BLS, Treasury, Federal Reserve, NY Fed, World Bank, OECD, GDELT and SEC summary/status data).
- `sec_tickers.json`: SEC ticker/CIK/exchange mapping staged server-side because SEC endpoints do not support browser CORS reliably.
- `liquidity_public.json`: no-key U.S. liquidity/policy plumbing data (Treasury operating cash/TGA, NY Fed repo/reverse-repo results, and Federal Reserve-published balance-sheet/policy series).
- `news_history.json`: legacy derived research archive copied from the prior public Market V2 preview; keep its provenance separate from the new live GDELT feed in `official_sources.json`.
- `market_history.json`, `market_snapshot.json`, `structure_lab.json`: only generated after the selected price-data licence explicitly permits public website display/static JSON. They must not be fabricated when the licence gate is closed.

Never put account balances, candidate orders, strategy/backtest files, API secrets or unlicensed vendor OHLCV in this public directory. This repository is website-only.
