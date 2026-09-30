# 来源与迁移说明

UI基线来自 2026-09-30 的 `market_research_terminal_v2_preview.zip`，对应源项目 `galbbb2772/market-indicators-v1` 的研究 Draft PR #5。新仓库 `galbbb2772/market-research-terminal` 为独立网站工作区；本仓库不是对原仓库历史的完整克隆，也不改变原仓库。

`docs/data/news_history.json` 来自原网站已经存在的派生评分档案（不是新闻原文）。在正式启用 GitHub Pages 前，仍应单独复核该档案及未来新接数据的公开使用和再分发条件。

`docs/data/structure_lab.json` 当前不存在。行情、行业ETF和宏观历史接口暂时只保留配置槽位；未来确定数据供应商、授权和字段口径后，再用 `tools/stage_data.py` 校验并放入网站。

本仓库不包含原策略仓库、账户资料或私有交易数据。
