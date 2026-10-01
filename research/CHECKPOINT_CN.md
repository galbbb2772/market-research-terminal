# Market Research Terminal｜可恢复研究检查点

更新日期：2026-10-01。发生对话消息流错误时，以仓库 `main` 的真实文件和最新 GitHub Actions 为准，而不是依赖聊天上下文。

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
7. `tools/enrich_cycle_research.py` 已接入周期研究数据层：对行业 ETF 计算“周收益 − SPY周收益”的1–26周 Pearson 历史自相关，并保留每个滞后的有效样本对。相关峰值只能称为历史相关峰值，不能直接称为已验证周期。
8. 周期研究同时生成4周相对SPY的横截面领导板块历史、领导权切换次数/切换率、中位连续领先周数、每周横截面覆盖，以及小/大箱体已结束样本的中位、均值、P25/P75/P90、最短/最长持续交易日。
9. 活跃度轮动已实现：记录每日活跃度第一行业、Top 3、切换率、中位连续第一交易日，并计算1/5/20交易日行业活跃度横截面排名 Spearman 持续性。
10. `tools/validate_cycle_research.py` 的收益周期严格验证层：三段连续历史时间切分、4周块置换近似双侧 p 值、4周 circular moving-block bootstrap 95%区间，以及 Benjamini-Hochberg FDR。
11. 1/5/20日活跃度排名持续性已升级到同级严格验证：验证器从 `sector_history` 重建每天完整行业活跃度横截面，而不是只检验三个汇总均值；每个滞后记录平均 Spearman、有效日期对、三段连续历史均值、5交易日 block permutation p、5交易日 moving-block bootstrap 95%区间、活跃度家族 FDR q，以及收益周期+活跃度全部假设合并后的研究级全局 FDR q。
12. 活跃度候选只有在研究级全局 q≤0.10，且至少三段历史中的两段与全样本 Spearman 方向一致时，才保留为研究候选；否则为校正后未获支持。该标签仍只是历史研究候选，不是预测或交易信号。
13. `docs/activity-validation.js` 已作为独立前端模块接入 `cycle-lab`，展示1/5/20日严格验证的 p/q/CI/三段均值/结论。
14. `docs/cycle-lab.html` 已展示1–26周自相关图、历史峰值、有效样本数、峰值块置换 p、行业/全局 q、95%块bootstrap区间、三段历史相关、严格验证汇总、4周相对SPY领导板块、活跃度轮动和箱体持续期分布。
15. `tools/stage_data.py` 已兼容指数没有成交量的真实市场数据。
16. 已有 Tiingo ETF 和 Massive 四大指数授权适配器。`refresh-licensed-etfs.yml` / `refresh-licensed-indices.yml` 在获授权后依次执行：合并真实历史 -> 生成箱体 -> 生成轮动描述 -> 严格周期/活跃度验证 -> 生成市场快照 -> 仅提交获准公开的数据文件。
17. 测试已覆盖箱体前视风险、空成交量、评分边界、周期描述、活跃度轮动、收益周期严格验证，以及活跃度1/5/20日严格验证的FDR/bootstrap/时间切分/确定性。
18. 已核验 IEX HIST 官方历史数据条款：IEX 允许再分发 IEX historical data，但必须按条款注明 IEX 数据来源和条款链接。IEX HIST 是 IEX 场内数据，不能冒充全市场 SIP / 综合 OHLCV；原始 PCAP 单日体积巨大，因此作为公开可追溯参考源，不直接承担本项目长期综合 ETF 日K主源。
19. 已核验 Tiingo Developer Program：软件可要求每个用户提供自己的 Tiingo API Token，并用该用户 Token 直接请求 Tiingo，而软件本身不再分发数据；这种 BYO Token 模式不需要开发者另取 redistribution licence，但必须遵守 Tiingo 开发者规则并清楚标注数据源。
20. `docs/personal-data.html` + `docs/personal-tiingo.js` 已实现 Personal Real Data Mode：Token 只存在当前浏览器内存，不进 GitHub、不进 localStorage/sessionStorage、不写公开 JSON；页面直接请求 SPY / QQQ / DIA + 11 个 S&P 行业 ETF 的 Tiingo EOD。
21. Personal Real Data Mode 已升级为完整个人研究终端：`docs/personal-research-worker.js` 在独立 Web Worker 中接收**不含 Token**的标准化日K，计算20/60日完整历史箱体、形成/稳定/难度/综合评分、60日行业量价活跃度历史、4周相对SPY领导权、1–26周相对收益自相关、1/5/20日活跃度 Spearman，以及块置换、moving-block bootstrap、FDR 和研究级全局校正。
22. `docs/personal-research.js` 在同一 Personal 页面显示历史箱体数量和当前箱体、领导板块、活跃度轮动、1/5/20严格显著性、各行业收益周期峰值 p/q/CI/三段历史和最终“保留候选/未获支持”。最终展示门槛使用研究级全局 q≤0.10 + 至少2/3时间段方向一致。
23. 个人完整链采用 200 次重采样；收益周期使用4周 block，活跃度使用5交易日 block。重计算放在 Web Worker，避免阻塞手机/浏览器主界面。
24. `tests/test_personal_research.py` 与 CI 已保护 Personal 页挂载、Token 隔离、20/60及14%/28%参数、1/5/20与1–26周期、200次重采样、block permutation / bootstrap / research-wide FDR；`personal-research.js` 与 `personal-research-worker.js` 均进入 `node --check`。
25. 2026-10-01 最新完整个人真实数据研究链提交通过完整 GitHub Validate：Python 编译、全部单元测试和全部前端 JavaScript 均成功。
26. `research/DATA_SOURCE_RIGHTS_CN.md` 已记录 IEX / Tiingo / Massive / Alpha Vantage / Nasdaq Data Link / FMP / Twelve Data / Stooq 的当前权限判断与用途边界。
27. 私有真实数据验证已实际启动：通过 Massive 连接器取得 SPY / QQQ / DIA / XLK / XLF 各约501个真实日K；随后触发当前套餐 rate limit。Financial Datasets 当前余额为0，Longbridge 当前历史K线配额为0，因此均不作为本轮继续抓取路径。

## 尚未完成／不能假装已完成

- 公开 `docs/data/market_history.json`、`docs/data/structure_lab.json`、`docs/data/market_snapshot.json` 仍没有一套“综合美股 ETF EOD + 允许本站统一静态再分发”的长期主源。IEX HIST 虽具备可再分发路径，但仅代表 IEX 场内且 PCAP 过重；Tiingo 普通 API 若由本站统一缓存/再分发仍需单独 redistribution permission。
- Personal Real Data Mode 的浏览器直连仍需用用户自己的真实 Tiingo Token 在目标浏览器验证 CORS/网络表现；若被浏览器策略阻止，改用本机 `tools/fetch_licensed_etfs.py` 的 internal-only 输出路径，不降低授权要求。
- 行情获授权前，公开结构页和周期页继续明确显示等待真实公开数据，不显示模拟箱体或模拟周期；个人模式与公开模式必须保持分离。
- 社交/新闻题材关注度尚未接入。当前“行业活跃度”仍是量价代理，而非注意力数据。
- 当前“时间切分”是历史稳定性检查，不等同于真正的滚动 walk-forward/OOS 预测检验；不能宣称未来预测能力。
- 块置换、bootstrap 与 FDR 只提高历史依赖检验的严谨性，不等于因果证明，也不等于有可交易收益。
- FRED完整宏观历史系列与宏观周期研究仍未完成。
- 20/60日、14%/28%、评分公式尚未经独立统计/收益验证，不应宣称有预测力。

## 恢复步骤

1. 读取本文件、`research/DATA_SOURCE_RIGHTS_CN.md`、`research/METHODS_CN.md`、`research/MARKET_DATA_CONTRACT_CN.md`；查看 `main` 最新提交及 Actions 的 Validate/Deploy 最新运行结果。
2. 优先验证 `docs/personal-data.html` 的 Tiingo BYO Token 浏览器直连：输入用户自己的 Token 后应依次看到真实行情覆盖、完整历史箱体、4周领导权、活跃度1/5/20严格验证、收益周期严格验证。不要把 Token 发到聊天、提交 GitHub、写进 URL 日志或公开 JSON。
3. Personal 页若成功直连，后续研究优先基于这条真实个人数据链继续扩展；原始行情只留在当前浏览器内存，Web Worker payload 只包含标准化日K。
4. 查看 `docs/data` 是否真实存在获授权市场 JSON。不要为了让网页有图而塞模拟数据。公开统一数据仍只接受明确 public-display / redistribution 权限。
5. 检查 `structure-lab.html` 当前状态卡、周/月/年K缺失成交量、行业 ETF 活跃度表和历史箱体切换。
6. 检查 `cycle-lab`：1–26周收益自相关、收益周期严格 p/q/CI/时间切分、4周相对SPY领导权、活跃度轮动、1/5/20日活跃度严格显著性、箱体持续期。任何通过项都只能称为“当前检验下保留候选”。
7. 私有研究可继续利用允许的连接器数据验证算法；受限原始行情不得复制进公开 GitHub。
8. 下一研究任务可进入真正 rolling walk-forward/OOS 稳定性研究，或返回第一页其余需求；严格验证通过也不直接转成策略收益宣传。
