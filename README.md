# Market Research Terminal

**独立美股市场结构与周期可视化网站**。当前只做网站、数据展示框架、数据接口占位配置和GitHub Actions静态检查/手动部署流程。**本仓库不包含回测、策略验证、样本外评估或实盘交易模块。**

## 本版页面

- `docs/index.html`: 网站首页 / 六大模块入口 + 已归档新闻曲线
- `docs/structure-lab.html`: 历史箱体、日K分布、行业活跃度、宏观观测界面
- `docs/cycle-lab.html`: 周期结构观察页面，仅展示历史自相关、箱体持续期等描述性统计（没有经核实数据时仅显示待接入）
- `docs/research-terminal-v2.css` / `.js`: 研究终端视觉、时间区间、箱体评分卡和交互扩展
- `docs/data/news_history.json`: 已有短期派生新闻评分历史；发布前仍需确认使用许可
- `config/data_sources.json`: 未来外部数据源接入槽位；**行情、ETF、宏观历史接口目前未接入这个新仓库**
- `tools/stage_data.py`: 在授权并取得真实数据之后校验本地数据文件的发布工具，不抓取任何接口

## 本地看网站

运行：`python -m http.server 8000 --directory docs`，在浏览器打开 `http://127.0.0.1:8000/`。手机端可查看页面，部分行情图表会明确标记“等待真实数据发布”，这是设计行为。

## GitHub 仓库

公开仓库：`galbbb2772/market-research-terminal`。本仓库只承载研究网站、图表、数据接口占位配置、数据发布校验和部署流程。

**请勿把访问令牌或API Key提交到仓库或发到聊天。**

## 发布机制（默认停用）

默认只有独立CI静态检查，没有自动公开GitHub Pages发布。`.github/workflows/deploy.yml` 只能手动触发，而且需要你在GitHub Repo Variables明确设置 `WEBSITE_DEPLOY_AUTHORIZED=true` 以及 `DATA_RIGHTS_APPROVED=true`；核验新闻存档与以后新接数据的再分发权后才允许开启。上线前对已发布数据与网站权限分别复核。

当前**已建立独立公开GitHub仓库**；新市场数据接口仍待后续接入，GitHub Pages默认未启用。
