# 个股结构研究流水线（Small / Large / Macro）

状态：2026-10-01 起进入研究冻结阶段。Small / Large V2 已完成人工验收，除非出现明确反例，不再为了单张图调整参数。Macro 作为独立长周期层继续记录，但不反向修改 V2。

## 1. 增量 Alpha 验证

`docs/stock-research.html` 在用户本机浏览器对缓存个股日K做 walk-forward 事件提取。只从结构正式 `detected_at` 之后统计“进入底部区”的事件，计算 1 / 3 / 5 / 10 / 20 交易日前瞻收益、胜率、MAE、MFE，并与非结构事件控制样本比较。页面给出快速近似 p 值用于筛选研究方向；正式显著性结论仍应使用 block permutation / bootstrap / FDR。

## 2. 每日候选名单

批量扫描结果按“研究优先度”排序，输入包括：

- 个股 Small / Large / Macro 当前位置；
- 个股成交额与日内振幅活跃度；
- 行业 ETF 的结构与活跃度；
- 题材 ETF 活跃度；
- SPY regime；
- 可选的 Frozen signal JSON 同日匹配。

该排序只是研究队列，不是买卖建议，也不触发下单。

## 3. 批量扫描

股票池可来自：文本输入、TXT/CSV、或浏览器 IndexedDB 已缓存股票。Tiingo Token 只留在当前页面内存。首次扫描从设定起始日获取，后续默认仅回补缓存最后日期前约 35 日并按日期去重，以处理供应商历史修订和最近复权变化。

## 4. 复权口径

新数据优先使用供应商明确提供的 adjusted OHLCV。旧缓存继续由拆股识别 / 回溯修正层兜底。个人 PowerShell 与 Python Tiingo 下载器也已切换到 provider-adjusted-first 口径。

## 5. 市场 / 行业 / 题材联动

浏览器读取用户自己保存的 ETF Bundle，不把受限行情发布到 GitHub。行业/题材映射优先使用 Tiingo 元数据；元数据不足时允许研究页只显示已确认上下文，不伪造分类。

## 6. 生产化约束

- 引擎版本写入 `docs/data/structure_engine_manifest.json`；
- 页面显示逐股票扫描进度、数据新鲜度和失败状态；
- 候选和 Alpha 结果可导出 JSON，导出中不包含原始日K；
- 个股原始 Tiingo 行情只存在用户本机 IndexedDB；
- GitHub Pages 不静态再分发个股 Tiingo 日K；
- 当前无实盘执行模块。

## Frozen 接口

研究页接受数组或包含 `signals` / `candidates` / `rows` 的 JSON。每条记录至少需要：

- `symbol` / `ticker` / `id`
- `date` / `session` / `signal_date`

导入后可在每日候选表显示同日重合，也可勾选“只统计与 Frozen 同日重合的结构事件”做条件验证。
