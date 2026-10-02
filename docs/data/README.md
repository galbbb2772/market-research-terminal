# Published data directory

Public/static outputs in this directory are split by rights and purpose:

- `official_sources.json`: generated daily from no-key official/open sources (BLS, Treasury, Federal Reserve, NY Fed, World Bank and OECD, plus fail-soft SEC/GDELT status attempts).
- `liquidity_public.json`: no-key U.S. liquidity/policy plumbing data (Treasury operating cash/TGA, NY Fed repo/reverse-repo results, and Federal Reserve-published balance-sheet/policy series).
- `positioning_public.json`: CFTC public TFF futures positioning for selected major equity-index, U.S. dollar and Treasury contracts. Contract counts and net positions are descriptive context, not dollar or ETF flows.
- `news_public.json`: resilient recent news context. GDELT aggregate timelines are attempted first; official Federal Reserve and BLS RSS release headlines/links provide a no-key fallback. Article bodies are not republished.
- `sec_tickers.json`: optional SEC ticker/CIK/exchange mapping when the SEC endpoint permits access. Hosted GitHub runners currently receive HTTP 403, so absence of this file must not break refreshes; it is not required for the present ETF/index scope.
- `news_history.json`: legacy derived research archive copied from the prior public Market V2 preview; keep its provenance separate from the new live public-news output.
- `market_history.json`, `market_snapshot.json`, `structure_lab.json`: only generated after the selected price-data licence explicitly permits public website display/static JSON. They must not be fabricated when the licence gate is closed.

Never put account balances, candidate orders, strategy/backtest files, API secrets or unlicensed vendor OHLCV in this public directory. This repository is website-only.
