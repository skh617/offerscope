# Offerscope

BOSS 直聘岗位追踪系统 — 抓取、分析、趋势对比、飞书推送，一站式岗位市场洞察。

## 核心能力

- **智能抓取** — 基于 CloakBrowser 反检测浏览器，自动登录、关键词搜索、触底翻页、详情页采集、全局去重
- **多维分析** — jieba 中文分词提取 JD 技能关键词，24 维雷达图自适应岗位类型，薪资/经验/学历分布可视化
- **趋势对比** — 支持多次抓取历史对比，薪资中位数环比、技能热度涨跌、高薪分水岭技能识别
- **飞书推送** — 一键推送交互卡片到飞书群，支持涨跌色彩标记和完整报告链接

## 快速开始

### 前置条件

| 依赖 | 要求 |
|------|------|
| Python | >= 3.9 |
| Node.js | >= 18（Playwright 前置） |
| 操作系统 | Windows / macOS / Linux |

### 1. 克隆项目

```bash
git clone <repo-url>
cd offerscope
```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv .venv

# Windows (Git Bash)
source .venv/Scripts/activate

# macOS / Linux
source .venv/bin/activate

pip install cloakbrowser playwright jieba pyyaml requests
```

> CloakBrowser 首次运行时会自动下载定制反检测 Chromium（约 200 MB）。如需手动安装，参考 [doc/init plan.md](doc/init%20plan.md)。

### 3. 配置抓取任务

编辑 [config.yaml](config.yaml)：

```yaml
tasks:
  - keyword: AI应用后端工程师   # 搜索关键词
    cities: [北京]               # 目标城市
    max_jobs: 10                 # 抓取数量上限
    webhook: https://open.feishu.cn/open-apis/bot/v2/hook/...  # 飞书机器人 Webhook
```

### 4. 运行

```bash
# 启动报告服务（保持后台运行）
python serve.py

# 执行全流程（会弹出浏览器，扫码登录后自动抓取→分析→推送）
python scheduler.py

# 或预览模式（使用已有数据，不抓取）
python scheduler.py --dry-run
```

首次运行会弹出 CloakBrowser 窗口，在浏览器中扫码或手机号登录 BOSS 直聘后，脚本自动继续。

## 架构

```
config.yaml  →  scheduler.py  →  tools/scraper.py   抓取 → data/*.json
                              →  tools/trend.py      趋势对比
                              →  tools/analyzer.py   分析 → reports/*.html
                              →  tools/publisher.py  推送 → 飞书卡片
```

模块通过 JSON 文件解耦，每个工具可独立运行：

| 模块 | 职责 | 独立运行 |
|------|------|----------|
| [tools/scraper.py](tools/scraper.py) | CloakBrowser 抓取 BOSS 直聘 | `python tools/scraper.py <keyword> <city> <code> [max]` |
| [tools/trend.py](tools/trend.py) | 历史对比：薪资环比、技能涨跌 | 仅被调度器调用 |
| [tools/analyzer.py](tools/analyzer.py) | 生成可视化 HTML 报告 | `python tools/analyzer.py`（自动选取最新 JSON） |
| [tools/publisher.py](tools/publisher.py) | 飞书交互卡片推送 | `python tools/publisher.py <jobs.json> --dry-run` |
| [serve.py](serve.py) | 本地 HTTP 报告服务（端口 8092） | `python serve.py` |

## 输出文件

```
offerscope/
├── data/                                   # 抓取数据
│   ├── ai应用后端工程师_北京_2026-06-04_jobs.json
│   └── ai应用后端工程师_北京_2026-06-04_jobs.csv
└── reports/                                # 分析报告
    └── ai应用后端工程师_北京_2026-06-04_分析报告.html
```

HTML 报告包含：岗位画像卡片、技能雷达图、薪资分布、经验/学历要求、技能高频词、高薪对比、岗位明细表（支持弹窗查看详情）。

## 城市编码

| 城市 | 编码 | 城市 | 编码 |
|------|------|------|------|
| 北京 | 101010100 | 上海 | 101020100 |
| 广州 | 101280100 | 深圳 | 101280600 |
| 杭州 | 101210100 | 成都 | 101270100 |
| 南京 | 101190100 | 武汉 | 101200100 |
| 西安 | 101110100 | 苏州 | 101190400 |

> 新增城市时需同步更新 [scheduler.py](scheduler.py#L189-L192) 和 [tools/scraper.py](tools/scraper.py) 中的 `CITY_CODES` 映射。

## 常见问题

**Q: 浏览器弹出后一直显示登录页？**  
CloakBrowser 首次使用需要手动登录 BOSS 直聘。登录成功后浏览器会话会被持久化，后续运行自动复用。

**Q: 抓取中途报错？**  
脚本内置渐进式限流恢复机制（连续错误时等待时间从 30s 逐步延长到 90s）。如果长时间卡住，检查网络或重新运行。

**Q: 飞书卡片点击链接无法打开报告？**  
飞书不支持 `file://` 协议和中文 URL。解决方案：先启动 `python serve.py`，卡片中的 `/report/ai` 短链接由 serve.py 路由到实际文件。

**Q: Windows 终端显示乱码？**  
Windows 默认 GBK 编码无法显示部分字符。使用 Git Bash 或 Windows Terminal 运行。

## 技术要点

- **反检测** — CloakBrowser 定制 Chromium 隐藏 `navigator.webdriver`，配合随机延迟（3-8s）模拟人类行为
- **无限滚动翻页** — `scrollTo(bottom)` 触底 + DOM 卡片数量变化监测
- **全局去重** — 按岗位 `link` 去重，不同关键词搜到的同一岗位不会重复采集
- **动态关键词** — jieba 从 JD 文本自动提取高频技能词，不依赖写死列表
- **自适应雷达** — 24 维候选池覆盖技术/商务/财务等维度，自动选 8 个最相关的展示
