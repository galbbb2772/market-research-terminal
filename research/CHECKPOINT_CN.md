# Market Research Terminal｜可恢复研究检查点

更新日期：2026-09-30。发生对话消息流错误时，以仓库 `main` 的真实文件和最新 GitHub Actions 为准，而不是依赖聊天上下文。

## 当前唯一工作范围

- 独立美股市场研究网站；此仓库不承载 Frozen V4 策略回测或个股/退市股数据库。
- 本阶段只纳入 SPY / QQQ / DIA、S&P 500、Nasdaq-100、Nasdaq Composite、DJIA、已确认映射的行业 ETF/指数。
- 绝不向公开网站写入模拟行情、凭空生成的历史K线或来源不明的公开再分发数据。
- `QQQ` 跟踪 Nasdaq-100，不能代替 Nasdaq Composite。

## 已实现

1. `docs/structure-lab.html`：日/周/月/年K、历史大/小箱体、编号、上下沿、实际持续交易日、形成度/稳定度/交易难度/综合评分、日K涨跌分布、行业活跃度/相对 SPY、已有新闻紧张度、宏观占位。
2. 顶部“当前箱体状态”：最近真实收盘、小/大箱体是否仍进行、箱体内 0–100% 位置、底/中/顶部区、距上下沿百分比、持续交易日、四项评分。它是当前结构描述，不是交易信号。
3. 周/月/年聚合对指数 `volume=null` 保持缺失，不会伪装成成交量0。
4. `tools/build_structure_lab.py`：从已取得的真实 `MARKET-HISTORY-V1` 自动构建 `STRUCTURE-LAB-V1`，不抓取/发明原始行情。20日小箱体宽度阈值14%，60日大箱体28%，上下边界各至少2次触碰；边界带为箱体高度12%。这些是待验证的研究启发式参数，不是经收益优化的定论。
5. 箱体 `detected_at` 只在达到条件的那根日K收盘后确认；上下沿确认后固定，后续日K收盘突破时结束。已完成箱体最终评分属于事后描述，不能直接当历史实时特征使用。
6. 行业 ETF 活跃度 = 当日成交金额相对前60个交易日百分位与日内振幅百分位的均值，0–100。不可称之为真实资金净流入、新闻热度或社交关注度。
7. `tools/stage_data.py` 已兼容指数没有成交量的真实市场数据。
8. 已有 Tiingo ETF 和 Massive 四大指数授权适配器，`refresh-licensed-etfs.yml` 和 `refresh-licensed-indices.yml` 会在获授权后从历史数据依次生成 `structure_lab.json` 和 `market_snapshot.json`。
9. `tests/test_structure_builder.py` 测试未来数据不会把 `detected_at` 提前、空成交量、评分0–10。`tests/test_site.py` 保护当前状态页面和无虚构数据要求；已改为允许通过合法验证的公开行情文件入库。

## 尚未完成／不能假装已完成

- 公开 `docs/data/market_history.json`、`docs/data/structure_lab.json`、`docs/data/market_snapshot.json` 仍须由**具备明确公开网站展示和静态缓存许可**的真实数据生成。仅拥有个人 API Key 并不等于拥有公开再分发权。
- 行情获授权前，结构页会明确显示等待真实数据，不显示模拟箱体。
- 社交/新闻题材关注度、FRED完整历史系列与行业轮动周期的统计检验尚未完成。当前行业活跃度是量价代理，而非注意力数据。
- 20/60日、14%/28%、评分公式尚未经独立统计/收益验证，不应宣称有预测力。
- GitHub Pages 部署可能处于 `pending`；代码验证通过不代表最新页面已经发布。每次恢复先检查最新 Actions，再核对在线网站。

## 恢复步骤

1. 读取本文件和 `research/METHODS_CN.md`、`research/MARKET_DATA_CONTRACT_CN.md`；查看 `main` 最新提交及 Actions 的 Validate/Deploy 最新运行结果。
2. 查看 `docs/data` 是否真实存在获授权市场 JSON。不要为了让网页有图而塞模拟数据。若尚未授权，先处理数据许可证及 GitHub Secrets/Variables；不要在聊天或前端粘贴 API Key。
3. 检查 `structure-lab.html` 当前状态卡、周/月/年K缺失成交量、行业 ETF 活跃度表和历史箱体切换。
4. 如网页尚未部署，优先诊断 `Deploy research website` 的 queued/pending、仓库 Pages 环境与权限，再处理其他页面美化。
5. 授权配置完备后，通过既有工作流构建真实历史，并核验其时间覆盖、标的数量、箱体数量和延迟时间。先描述性检验，再考虑周期统计，暂不做策略收益回测。
