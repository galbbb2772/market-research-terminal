# Market Research Terminal｜行情数据权限与接入路径

更新日期：2026-10-01。此文件用于防止把“能调用 API”误写成“能公开再分发”。公开 GitHub Pages、个人浏览器数据和 ChatGPT 私有研究必须分开处理。

## 1. IEX HIST：可公开再分发，但不是全市场综合行情

- 官方入口：https://iextrading.com/trading/market-data/
- 历史数据条款：https://www.iex.io/legal/hist-data-terms
- IEX HIST 对公众免费提供 T+1 历史 PCAP。
- IEX 历史数据条款明确允许 distribute / sell / lease / furnish / otherwise provide access，但再分发时必须按条款注明 IEX 数据来源与条款链接。
- 重要限制：这些成交/报价只反映 IEX Exchange，自身并不代表 NYSE/Nasdaq/全市场 SIP 的综合 OHLCV；不能把 IEX-only bar 标成“美国全市场官方日K”。
- 工程限制：原始 PCAP 单日通常为数 GB 到十余 GB，长期全历史直接塞进 GitHub Actions 并不现实。

结论：IEX HIST 可以作为**公开、可追溯、场内参考数据源**，适合微观结构/场内成交研究和抽样验证；不直接代替本项目的综合 ETF EOD 主源。

## 2. Tiingo：公开静态再分发需要单独许可；BYO Token 开发者模式可用

- API 总览：https://www.tiingo.com/documentation/general
- Developer Program：https://www.tiingo.com/documentation/appendix/developers
- EOD 文档：https://www.tiingo.com/documentation/end-of-day

普通 Basic / Power / Commercial API 数据均不是自动获得公开再分发权。若把 Tiingo 原始数据写进公开 JSON、公开网站或 App 后端统一分发，需要单独 redistribution permission / licence。

Tiingo Developer Program 另行明确允许一种模式：软件要求**每个用户自己提供自己的 Tiingo API Token**，软件直接用该用户 Token 请求 Tiingo，并且软件本身不再分发数据。该模式无需开发者另外取得 redistribution licence，但需清楚标注 Tiingo 为数据源，并遵守其开发者规则。

因此本仓库采用两种互斥模式：

1. `tools/fetch_licensed_etfs.py --publish`：只有在存在明确书面 PUBLIC WEBSITE DISPLAY / static JSON 权限时才允许写入 `docs/data`。
2. Personal / BYO Token 模式：Token 只在用户自己的浏览器会话或本机环境使用；不提交 GitHub、不写入公开 JSON、不由本站统一转发。

## 3. Massive：仅用于当前连接下的私有研究验证

Massive 当前 Market Data Terms 默认个人/非商业使用，并限制向第三方公开展示、再分发以及基于其行情的 Derived Works，除非另有明确许可/商业安排。因此 ChatGPT 中通过 Massive 连接器取得的数据只能作为当前用户的私有分析材料，不应写入公开 Pages 数据文件。

2026-10-01 实测当前连接可取 SPY / QQQ / DIA / XLK / XLF 日K，但一次长日期请求只返回约 501 个交易日，并很快触发当前套餐 rate limit。这是一条可用于真实样本验证的私有数据路径，不是公开发布路径。

## 4. 其他已核验供应商

- Alpha Vantage：默认个人/非商业权限；公开/商业展示需另行商业安排。
- Nasdaq Data Link：数据使用/分发范围由订单与第三方数据条款限定，不能把普通访问权视为公开再分发权。
- Financial Modeling Prep：公开网站/客户端展示及再分发要求 Data Display and Licensing Agreement。
- Twelve Data：个人方案禁止 redistribution；外部展示/再分发依赖 Business / Redistribution Rights Add-On 或单独协议。
- Stooq：能公开下载并不等于存在明确的再分发许可；目前未找到足以支撑本公开站静态缓存/再发布的官方授权文本，因此不作为公开主源。

## 5. 本项目当前采用的原则

- **公开站**：只发布官方公共来源、明确许可来源或取得书面 public-display 权限的数据。
- **个人真实数据模式**：用户自己的 Token -> 用户自己的浏览器/本机 -> 只供该用户研究；Token 不上传本站。
- **ChatGPT / 私有验证**：可以使用已连接的个人市场数据工具验证算法，但不把受限原始数据复制到公开 GitHub。
- 所有来源都保留 provider、rights status、检索时间、数据范围和限制说明。
