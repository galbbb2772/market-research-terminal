# Market Research Terminal

独立的 **美国大盘 / 行业结构 / 宏观 / 新闻 / 历史结构** 可视化网站。

当前正式范围已经固定为：**ETF + 主要指数**。本仓库不建设全美股个股数据库，不需要退市股历史，不包含策略回测、Sharpe、OOS、实盘交易或 Frozen V4 策略代码。

## 当前页面

- `docs/index.html`：统一研究首页，大盘核心资产 + 六个研究模块
- `docs/sector-map.html`：S&P 500 / Nasdaq-100 / Dow Jones U.S. 三套行业地图
- `docs/instrument.html`：统一指数 / ETF 详情页，预留真实日K、1D/5D/20D、波动率、回撤、相对SPY和箱体
- `docs/structure-lab.html`：历史箱体、日K分布、行业活跃度、宏观观测
- `docs/cycle-lab.html`：历史自相关、箱体持续期等描述性周期结构
- `docs/news-archive.html`：现有短期新闻紧张度五项分量存档
- `docs/api-status.html`：官方公共数据接口状态

## 市场范围

### 大盘 ETF

- SPY
- QQQ
- DIA

### 主要指数

- S&P 500
- Nasdaq-100
- Nasdaq Composite
- Dow Jones Industrial Average

QQQ 跟踪 Nasdaq-100，**不是** Nasdaq Composite；网站内始终分开处理。

### S&P 500 一级行业 ETF

`XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY`

### Nasdaq-100 行业

按 Nasdaq 官方行业分类。只有在官方行业指数或对应 ETF 的准确映射被核验后，才加入代码；不能为了凑齐 11 个行业而虚构映射。

### Dow Jones 行业

使用更广泛的 Dow Jones U.S. Sector / Industry Index 家族，而不是把 30 只 DJIA 成分股硬拆成完整行业指数体系。

## 行情数据合同

- `docs/data/market_universe.json`：网站允许出现的指数 / ETF / 行业体系
- `docs/data/market_snapshot.schema.json`：首页和行业热力图小型快照合同
- `docs/data/market_history.schema.json`：统一历史日K合同
- `research/MARKET_DATA_CONTRACT_CN.md`：计算口径与公开展示规则

公开 GitHub Pages 只能读取经核准为 `verified_publishable` 的行情数据。缺数据时页面明确显示等待数据，不生成演示行情或模拟历史。

## 数据管线

目标结构：

`数据源 -> GitHub Actions / 服务端抓取 -> 清洗 -> 标准 JSON -> docs/data -> 静态网页`

API Key 不写入网页 JavaScript，也不要提交到公开仓库。

## 现有官方公共数据

宏观与金融条件方向已经建立 BLS、U.S. Treasury、Federal Reserve、NY Fed、OECD、World Bank 等官方来源的抓取/探针框架；行情数据源仍单独按公开展示许可筛选。

## 网站

GitHub Pages 已启用；仓库：`galbbb2772/market-research-terminal`。
