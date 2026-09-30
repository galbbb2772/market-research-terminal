# 市场行情数据合同（当前正式范围）

本网站的行情范围固定为 **ETF + 主要指数**，不建设全美股数据库，不需要个股退市历史。

## 1. 核心大盘

- ETF：SPY、QQQ、DIA
- 指数：S&P 500、Nasdaq-100、Nasdaq Composite、Dow Jones Industrial Average

QQQ 与 Nasdaq Composite 必须分开：QQQ 跟踪 Nasdaq-100。

## 2. 行业体系

- S&P 500：11 个 Select Sector SPDR ETF（XLB/XLC/XLE/XLF/XLI/XLK/XLP/XLRE/XLU/XLV/XLY）
- Nasdaq-100：按 Nasdaq 官方行业分类；只在官方行业指数或对应 ETF 映射核验后加入代码。不能硬凑 11 个行业 ETF。
- Dow Jones U.S.：使用 Dow Jones U.S. Sector / Industry Index 家族；不是把 30 只 DJIA 成分股硬拆成行业指数。

## 3. 两层 JSON

### `market_snapshot.json`

给首页、行业热力图使用的小型快照：1D、5D、20D、20D 波动率、距高点回撤、相对 SPY、活跃度、箱体状态。

### `market_history.json`

统一历史日 K。每根 bar 为：

`[date, open, high, low, close, volume|null, adjusted_close|null]`

指数没有可靠成交量时必须写 `null`，不得自行制造成交量。

## 4. 许可规则

公开 GitHub Pages 只读取 `rights_status=verified_publishable` 的行情数据。个人版、internal-only、non-display 或授权待确认的数据不能提交为公开行情文件。

API Key 永远放在 GitHub Secrets / 服务端抓取层，不进入网页 JavaScript。

## 5. 计算规则

- 1D/5D/20D：收盘价历史收益
- 20D 波动率：最近日收益样本标准差 × sqrt(252)
- 距高点回撤：最新收盘 / 可用历史最高收盘 - 1
- 相对 SPY 20D：标的 20D 收益 - SPY 同期 20D 收益
- 活跃度：如果使用成交额/振幅百分位代理，必须明确写“活跃度代理”，不得解释为资金净流入
- 箱体：来自独立结构计算，不从价格快照伪造

## 6. 当前禁止范围

- 个股全市场历史
- 退市股数据集
- 成分股生存偏差修正数据库
- 策略回测 / Sharpe / OOS / 实盘交易
