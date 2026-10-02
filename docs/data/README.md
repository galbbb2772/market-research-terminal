# Published data directory

Public/static outputs in this directory are split by rights and purpose:

- `official_sources.json`: generated daily from no-key official/open sources (BLS, Treasury, Federal Reserve, NY Fed, World Bank and OECD, plus fail-soft SEC status attempts).
- `liquidity_public.json`: no-key U.S. liquidity/policy plumbing data (Treasury operating cash/TGA, NY Fed repo/reverse-repo results, and Federal Reserve-published balance-sheet/policy series).
- `positioning_public.json`: CFTC public TFF futures positioning for explicitly pinned financial-futures contract codes. Contract counts and net positions are descriptive context, not dollar or ETF flows.
- `news_public.json`: resilient recent news context. GDELT aggregate timelines are attempted with bounded timeouts; official release feeds provide fallback context when available. Article bodies are not republished.
- `sec_tickers.json`: optional SEC ticker/CIK/exchange mapping when the SEC endpoint permits access. Hosted GitHub runners currently receive HTTP 403, so absence of this file must not break refreshes; it is not required for the present ETF/index scope.
- `news_history.json`: legacy derived research archive copied from the prior public Market V2 preview; keep its provenance separate from the new live public-news output.
- `market_history.json`: canonical ETF daily history can be generated from HF Data Library after `HFDL_API_KEY` is configured. The provider publishes the dataset under CC BY 4.0. The JSON preserves the March-2022 PiTrading-to-IEX-only source break and required attribution. Proprietary headline indices are not fabricated.
- `structure_lab.json` and `market_snapshot.json`: derived from `market_history.json` only when the upstream history is marked `rights_status=verified_publishable`.

The public attribution page is `../open-data-attribution.html`.

Never put account balances, candidate orders, strategy/backtest files, API secrets or unlicensed vendor OHLCV in this public directory. This repository is website-only.
