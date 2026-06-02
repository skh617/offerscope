# BOSS直聘职位抓取与分析 — Quick Start

使用 CloakBrowser 反检测浏览器抓取 BOSS直聘职位数据，jieba 自动提取 JD 技能关键词，生成花叔Design 风格可视化 HTML 报告。

## 前置要求

| 依赖 | 最低版本 |
|------|----------|
| Python | >= 3.9 |
| Node.js | >= 18 |
| 操作系统 | Windows / macOS / Linux（需要有图形界面） |

## 安装

### 1. 安装 Claude Code Skill

在 Claude Code 终端中执行：

```
claude /install-skill https://github.com/TreeWalk/boss-zhipin-skill
```

或手动克隆：

```bash
git clone https://github.com/TreeWalk/boss-zhipin-skill.git ~/.claude/skills/boss-zhipin
```

### 2. 初始化抓取环境

在 Claude Code 对话中说：

```
配置boss抓取
```

这会自动完成：
- 创建 Python 虚拟环境（`.venv`）
- 安装 CloakBrowser（反检测 Chromium）+ Playwright
- 下载 CloakBrowser 定制反检测浏览器（~200 MB）
- 验证 `navigator.webdriver` 为 `false`

> **网络提示**：CloakBrowser 定制 Chromium 约 200 MB，从 `cloakbrowser.dev` 下载。如果网络较慢，可手动下载后放到 `~/.cloakbrowser/chromium-146.0.7680.177.5/`（确保 `chrome.exe` 在该目录下）。

## 快速开始

### 三步工作流

```
配置boss抓取  →  抓取XX的XX岗位  →  分析岗位数据
```

### Step 1: 配置环境（仅首次）

```
配置boss抓取
```

### Step 2: 抓取职位

```
抓取北京的AI应用开发岗位
```

脚本会自动：
1. 弹出浏览器 → 扫码/手机号登录 BOSS直聘
2. 登录成功后自动按关键词搜索 + 触底滚动翻页
3. 多关键词全局去重
4. 逐条进入详情页获取薪资和 JD 描述
5. 保存为 JSON + CSV

### Step 3: 生成分析报告

```
分析岗位数据
```

自动生成包含以下内容的 HTML 报告并打开：

| 模块 | 内容 |
|------|------|
| 岗位画像卡片 | 各方向岗位数、薪资范围、经验/学历要求、核心技能标签 |
| 技能雷达图 | 从 24 维候选池自动选 8 个最相关维度（技术/商务/财务自适应） |
| 薪资分析 | 月薪区间柱状图、P75/P25 动态阈值 |
| 经验与学历 | 环形图分布 |
| 技能需求 | jieba 从 JD 自动提取高频技能词 |
| 高薪技能对比 | 高薪岗位 vs 入门岗位技能差异 TOP5 |
| 岗位明细表 | JS 分页 + 省略号页码 + 点击弹窗查看完整 JD |

## 手动配置抓取参数

编辑 `scraper.py` 顶部的参数区：

```python
# ===== 用户参数 =====
KEYWORDS = ["AI应用开发", "AI开发工程师", "大模型开发", "AIGC开发"]
CITIES = {"北京": 101010100}
PAGES_PER_SEARCH = 1          # 每个关键词最多滚动轮数（每轮约15条）
MAX_JOBS = 20                 # 最终抓取数量上限
# ====================
```

| 参数 | 说明 |
|------|------|
| `KEYWORDS` | 搜索关键词列表，建议 3-5 组近义词拓宽覆盖面 |
| `CITIES` | 城市编码字典，见下方城市码表 |
| `PAGES_PER_SEARCH` | 滚动轮数，每轮约 15 条。设 5 可采满 ~90 条/关键词 |
| `MAX_JOBS` | 最终保存的上限，采集数量超限时自动截断 |

然后直接运行：

```bash
source .venv/Scripts/activate  # Windows (bash)
# 或
source .venv/bin/activate      # macOS / Linux

python scraper.py
```

### 城市编码表

| 城市 | 编码 | 城市 | 编码 |
|------|------|------|------|
| 北京 | 101010100 | 上海 | 101020100 |
| 广州 | 101280100 | 深圳 | 101280600 |
| 杭州 | 101210100 | 成都 | 101270100 |
| 南京 | 101190100 | 武汉 | 101200100 |
| 西安 | 101110100 | 苏州 | 101190400 |
| 长沙 | 101250100 | 重庆 | 101040100 |
| 天津 | 101030100 | 郑州 | 101180100 |
| 合肥 | 101220100 | 青岛 | 101120200 |
| 东莞 | 101281600 | 佛山 | 101280800 |
| 珠海 | 101280700 | 厦门 | 101230200 |

## 手动生成报告

```bash
source .venv/Scripts/activate
python tools/analyzer.py
```

默认使用 `data/` 下最新的 `*_jobs.json`。也可指定文件：

```bash
python -c "
import json
from tools.analyzer_redesign import analyze
with open('data/xxx_jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f)
with open('reports/xxx_分析报告.html', 'w', encoding='utf-8') as f:
    f.write(analyze(jobs))
print('报告已生成')
"
```

## 输出文件

```
project/
├── scraper.py                    # 抓取脚本
├── tools/
│   └── analyzer_redesign.py      # 分析报告生成器
├── data/                         # 抓取数据
│   ├── xxx_jobs.json             # JSON 格式（完整字段）
│   └── xxx_jobs.csv              # CSV 格式（可用 Excel 打开）
└── reports/                      # 分析报告
    └── xxx_分析报告.html         # 可视化 HTML 报告
```

### JSON 数据字段

| 字段 | 说明 |
|------|------|
| `name` | 岗位名称 |
| `salary` | 薪资（如 "20-35K·14薪"、"400-450元/天"） |
| `experience` | 经验要求（如 "3-5年"、"经验不限"） |
| `education` | 学历要求（如 "本科"、"硕士"） |
| `company` | 公司名称 |
| `location` | 工作地点 |
| `industry` | 行业 |
| `scale` | 公司规模 |
| `financing` | 融资阶段 |
| `description` | JD 描述（前 500 字符） |
| `keyword` | 搜索关键词 |
| `city` | 城市 |
| `link` | 岗位链接 |

## 目录结构

```
boss-zhipin-skill/
├── README.md
├── QUICK_START.md                # 本文档
└── skills/
    ├── boss-setup/skill.md       # 环境配置
    ├── boss-scrape/skill.md      # 职位抓取
    └── boss-analyze/skill.md     # 数据分析
```

## 技术要点

- **触底滚动翻页**：BOSS直聘使用无限滚动加载，脚本通过 `scrollTo(bottom)` 触底并监测 DOM 卡片数量变化判断加载完成
- **多关键词全局去重**：按岗位 `link` 去重，不同关键词搜到的同一岗位不会重复
- **渐进式限流恢复**：详情页连续错误时，等待时间从 30 秒渐变到 90 秒
- **jieba 自动关键词提取**：从 JD 文本动态提取高频技能词，不依赖写死的关键词列表
- **P75/P25 动态阈值**：高薪/低薪线根据实际数据分布自动计算
- **24 维候选雷达**：覆盖技术/商务/外贸/财务/通用维度，自动选 8 个最相关的

## 常见问题

**Q: 浏览器弹出后一直显示登录页？**
需要在浏览器中手动扫码或手机号登录 BOSS直聘，登录成功后脚本自动检测并继续。

**Q: 抓取中途报错暂停？**
脚本内置渐进式限流恢复机制，遇到连续错误会自动等待并重试。如果长时间卡住，检查网络或重启脚本。

**Q: 薪资/描述字段为空？**
详情页采集阶段被提前停止了。确保脚本在列表采集完成后继续运行详情采集阶段。

**Q: 报告中文显示乱码？**
确保 HTML 文件用 UTF-8 编码保存，浏览器用 UTF-8 编码打开。

## License

MIT
