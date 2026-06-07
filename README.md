# Offerscope

BOSS 直聘岗位追踪系统 — 抓取、分析、趋势对比、飞书推送，一站式岗位市场洞察。

## 核心能力

- **智能抓取** — CloakBrowser 反检测浏览器，自动登录、关键词搜索、触底翻页、详情页采集、全局去重
- **多维分析** — jieba 中文分词提取 JD 技能关键词，24 维雷达图自适应岗位类型，薪资/经验/学历分布可视化
- **趋势对比** — 多次抓取历史对比，薪资中位数环比、技能热度涨跌、高薪分水岭技能识别
- **飞书推送** — 一键推送交互卡片到飞书群，涨跌色彩标记，完整报告链接
- **Web 服务** — 一键启动 Web 页面，分享链接给他人使用，远程扫码登录，零门槛体验

## 快速开始

### 前置要求

| 依赖 | 要求 |
|------|------|
| Python | >= 3.9 |
| Node.js | >= 18（Playwright 前置） |
| 操作系统 | Windows / macOS / Linux（需要图形界面） |

### 安装

```bash
git clone <repo-url>
cd offerscope

# 创建虚拟环境
python -m venv .venv

# 激活环境
source .venv/Scripts/activate   # Windows (Git Bash)
# source .venv/bin/activate     # macOS / Linux

# 安装依赖
pip install -r requirements.txt
```

> 首次运行 CloakBrowser 会自动下载定制反检测 Chromium（约 200 MB）。网络较慢时参考下方 [环境排障](#环境排障)。

### 启动

**方式一：Web 服务（推荐）**

```bash
python run_web.py
# → 浏览器打开 http://localhost:8090
```

打开页面 → 填岗位名 → 手机扫码登录 BOSS → 实时看进度 → 查看分析报告。

**方式二：CLI 命令行**

```bash
python run_cli.py              # 全流程（抓取 → 趋势 → 分析 → 推送）
python run_cli.py --dry-run    # 预览模式（使用已有数据，不抓取）
```

## 配置

编辑 [config.yaml](config.yaml)：

```yaml
tasks:
  - keyword: AI应用后端工程师   # 搜索关键词
    cities: [北京]               # 目标城市
    max_jobs: 10                 # 抓取数量上限
    webhook: https://open.feishu.cn/open-apis/bot/v2/hook/...  # 飞书 Bot Webhook（可选）
```

## 架构

### v2 Web 管道（推荐）

```
浏览器表单  →  offerscope/web.py (FastAPI)  →  offerscope/scraper.py   抓取 → storage/jobs/*.json
                                             →  offerscope/analyzer.py   分析 → storage/reports/*.html
                                             →  offerscope/publisher.py  推送 → 飞书卡片
```

### v1 CLI 管道

```
config.yaml  →  offerscope/cli.py  →  offerscope/scraper.py   抓取 → storage/jobs/*.json
                                    →  offerscope/trend.py      趋势对比
                                    →  offerscope/analyzer.py   分析 → storage/reports/*.html
                                    →  offerscope/publisher.py  推送 → 飞书卡片
```

模块通过 JSON 文件解耦，每个工具可独立运行：

| 模块 | 职责 | 独立运行 |
|------|------|----------|
| [offerscope/web.py](offerscope/web.py) | Web 服务入口（FastAPI） | `python run_web.py` |
| [offerscope/scraper.py](offerscope/scraper.py) | CloakBrowser 抓取 BOSS 直聘 | `python -m offerscope.scraper <keyword> <city> <code> [max]` |
| [offerscope/trend.py](offerscope/trend.py) | 历史对比：薪资环比、技能涨跌 | 仅被调度器调用 |
| [offerscope/analyzer.py](offerscope/analyzer.py) | 生成可视化 HTML 报告 | `python -m offerscope.analyzer`（自动选取最新 JSON） |
| [offerscope/publisher.py](offerscope/publisher.py) | 飞书交互卡片推送 | `python -m offerscope.publisher <jobs.json> --dry-run` |

## 项目结构

```
offerscope/
├── offerscope/                  ← Python 包
│   ├── scraper.py               ← BOSS 直聘抓取（CloakBrowser）
│   ├── analyzer.py              ← HTML 报告生成（Chart.js + jieba）
│   ├── trend.py                 ← 历史趋势对比
│   ├── publisher.py             ← 飞书卡片推送
│   ├── web.py                   ← FastAPI Web 服务
│   ├── cli.py                   ← CLI 调度入口
│   └── templates/
│       └── index.html           ← Web 前端 SPA
├── storage/                     ← 运行时数据
│   ├── jobs/                    ← 抓取数据（JSON + CSV）
│   └── reports/                 ← 分析报告（HTML）
├── boss-profile/                ← 浏览器持久化登录态
├── doc/                         ← 文档
│   ├── requirements/            ← 需求文档
│   ├── design/                  ← 设计文档
│   └── summaries/               ← 实现总结
├── config.yaml                  ← 任务配置
├── requirements.txt             ← Python 依赖
├── run_web.py                   ← Web 服务入口
└── run_cli.py                   ← CLI 调度入口
```

## 分析报告

HTML 报告包含以下模块：

| 模块 | 内容 |
|------|------|
| 岗位画像卡片 | 各方向岗位数、薪资范围、经验/学历要求、核心技能标签 |
| 技能雷达图 | 从 24 维候选池自动选 8 个最相关维度 |
| 薪资分析 | 月薪区间柱状图、P75/P25 动态阈值 |
| 经验与学历 | 环形图分布 |
| 技能需求 | jieba 从 JD 自动提取高频技能词 TOP15 |
| 高薪技能对比 | 高薪岗位 vs 入门岗位技能差异 |
| 岗位明细表 | JS 分页 + 点击弹窗查看完整 JD |

## 数据字段

每个岗位的 JSON 包含以下字段：

| 字段 | 说明 |
|------|------|
| `name` | 岗位名称 |
| `salary` | 薪资（如 "20-35K·14薪"） |
| `experience` | 经验要求（如 "3-5年"） |
| `education` | 学历要求（如 "本科"） |
| `company` | 公司名称 |
| `industry` | 行业 |
| `scale` | 公司规模 |
| `financing` | 融资阶段 |
| `description` | JD 描述（前 500 字符） |
| `keyword` | 搜索关键词 |
| `city` | 城市 |
| `link` | 岗位链接 |

## 城市编码

| 城市 | 编码 | 城市 | 编码 |
|------|------|------|------|
| 北京 | 101010100 | 上海 | 101020100 |
| 广州 | 101280100 | 深圳 | 101280600 |
| 杭州 | 101210100 | 成都 | 101270100 |
| 南京 | 101190100 | 武汉 | 101200100 |
| 西安 | 101110100 | 苏州 | 101190400 |

> 新增城市时需同步更新 [offerscope/web.py](offerscope/web.py) 和 [offerscope/cli.py](offerscope/cli.py) 中的 `CITY_CODES` 映射。

## 技术要点

- **反检测** — CloakBrowser 定制 Chromium 隐藏 `navigator.webdriver`，配合随机延迟（3-8s）模拟人类行为
- **无限滚动翻页** — `scrollTo(bottom)` 触底 + DOM 卡片数量变化监测
- **全局去重** — 按岗位 `link` 去重，不同关键词搜到的同一岗位不会重复采集
- **渐进式限流恢复** — 详情页连续错误时等待时间从 30s 逐步延长到 90s
- **动态关键词** — jieba 从 JD 文本自动提取高频技能词，不依赖写死列表
- **自适应雷达** — 24 维候选池覆盖技术/商务/财务等维度，自动选 8 个最相关的展示

## 常见问题

**Q: 浏览器弹出后一直显示登录页？**
首次使用需要在浏览器中手动扫码或手机号登录 BOSS 直聘。登录成功后会话持久化到 `boss-profile/`，后续自动复用。

**Q: 抓取中途报错？**
脚本内置渐进式限流恢复机制。长时间卡住时检查网络或重启。

**Q: 飞书卡片链接无法打开报告？**
通过 Web 服务（`python run_web.py`）访问报告，或直接在 `storage/reports/` 目录打开 HTML 文件。

**Q: Windows 终端显示乱码？**
Windows 默认 GBK 编码无法显示部分字符。使用 Git Bash 或 Windows Terminal 运行。

## 环境排障

以下是在 Windows 环境下配置时可能遇到的坑及解决方案：

| 序号 | 现象 | 原因 | 解决 |
|------|------|------|------|
| 1 | `pip install` 报 hash mismatch | pip 版本旧 / PyPI 下载慢 | 升级 pip + 用清华镜像：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>` |
| 2 | Playwright 安装被 kill (137) | CDN 下载太慢 | 手动下载 `chrome-headless-shell-win64.zip` 并解压到 `%LOCALAPPDATA%/ms-playwright/` |
| 3 | "An active lockfile is found" | 上次安装被 kill 后残留锁 | `rm -rf %LOCALAPPDATA%/ms-playwright/__dirlock` |
| 4 | `python -c` 报 `No such file` | bash 嵌套引号解析错误 | 改用临时 `.py` 脚本文件执行 |
| 5 | `launch()` 卡住很久 | 首次下载 200MB CloakBrowser Chromium | 耐心等待下载完成（约 300 秒），或手动放到 `~/.cloakbrowser/` |

### 手动安装 Playwright Chromium

如果自动下载超时，手动操作：

1. 获取正确版本号：运行 `python -m playwright install chromium` 被 kill 时从输出中复制 zip 链接
2. 浏览器下载 zip 文件（约 112MB）
3. 解压到 Playwright 缓存目录：
   ```bash
   mkdir -p "$HOME/AppData/Local/ms-playwright/chromium_headless_shell-1223"
   unzip -o chrome-headless-shell-win64.zip -d "$HOME/AppData/Local/ms-playwright/chromium_headless_shell-1223"
   touch "$HOME/AppData/Local/ms-playwright/chromium_headless_shell-1223/INSTALLATION_COMPLETE"
   ```
4. 验证：解压后必须有 `chrome-headless-shell-win64/chrome-headless-shell.exe`

### 验证环境

```bash
python -c "from cloakbrowser import launch; b=launch(headless=True); print('webdriver:', b.new_page().evaluate('navigator.webdriver')); b.close()"
```

输出 `webdriver: False` 表示反检测生效。
