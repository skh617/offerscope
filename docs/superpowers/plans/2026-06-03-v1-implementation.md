# BOSS直聘岗位追踪系统 v1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or inline execution.

**Goal:** 实现 config.yaml + scheduler.py + tools/trend.py + tools/publisher.py，修改 tools/scraper.py（函数化）+ tools/analyzer.py（弹窗加链接+删P75/P25）

**Architecture:** scheduler.py 读 config.yaml → 遍历 task×city → 串联 scraper→trend→analyzer→publisher，模块通过JSON路径解耦，单点失败不阻断

**Tech Stack:** Python 3, PyYAML, requests, jieba (已有)

---

### Task 1: config.yaml — 任务配置文件

**Files:**
- Create: `config.yaml`

- [ ] **Step 1: 创建 config.yaml**

```yaml
# BOSS直聘岗位追踪系统 - 任务配置
# 后续扩展字段: schedule(定时表达式), enabled(启停开关)

tasks:
  - keyword: Java后端开发
    cities: [北京]
    webhook: https://open.feishu.cn/open-apis/bot/v2/hook/placeholder-java

  - keyword: AI应用开发
    cities: [北京]
    webhook: https://open.feishu.cn/open-apis/bot/v2/hook/placeholder-ai
```

- [ ] **Step 2: 提交**

---

### Task 2: tools/scraper.py — 函数化重构

**Files:**
- Modify: `tools/scraper.py`

**重构目标:** 将硬编码参数改为函数参数，使 scheduler 可调用

- [ ] **Step 1: 将模块顶层参数移除，重构 main() 为可复用函数**

改动内容：
1. 移除顶层 KEYWORDS/CITIES/PAGES_PER_SEARCH/MAX_JOBS 硬编码
2. 新增 `scrape(keyword, city_name, city_code, max_jobs=40, pages_per_search=2)` 函数 — 返回 (jobs_json_path, jobs_list)
3. 保留 `login_wait()`, `collect_list()`, `collect_details()`, `save()` 不变
4. `main()` 改为从命令行参数读取或使用默认值，调用 `scrape()`

```python
# 替换顶层的 KEYWORDS/CITIES/PAGES_PER_SEARCH/MAX_JOBS 为:
DEFAULT_KEYWORDS = ["java后端开发"]
DEFAULT_CITIES = {"北京": 101010100}
DEFAULT_MAX_JOBS = 40
DEFAULT_PAGES = 2

def scrape(keyword, city_name, city_code, max_jobs=40, pages_per_search=2):
    """抓取单个关键词+城市的岗位数据
    Returns: (output_path, jobs_list)
    """
    ...
```

- [ ] **Step 2: 验证重构后仍可独立运行**

```bash
cd d:/AI\ Projects/offerscope && echo "验证 scraper.py 语法" && .venv/Scripts/python.exe -c "import tools.scraper; print('Import OK')"
```

---

### Task 3: tools/trend.py — 趋势对比模块

**Files:**
- Create: `tools/trend.py`

- [ ] **Step 1: 创建 tools/trend.py**

完整代码见下方实现。

- [ ] **Step 2: 用现有数据验证趋势计算**

```bash
python tools/trend.py data/java后端开发_jobs.json
```

---

### Task 4: tools/publisher.py — 飞书推送模块

**Files:**
- Create: `tools/publisher.py`

- [ ] **Step 1: 创建 tools/publisher.py**

完整代码见下方实现。

- [ ] **Step 2: 验证卡片组装逻辑**

```bash
python tools/publisher.py --dry-run data/java后端开发_jobs.json
```

---

### Task 5: tools/analyzer.py — 弹窗加链接 + 删除P75/P25

**Files:**
- Modify: `tools/analyzer.py`

- [ ] **Step 1: 弹窗 Modal 添加 BOSS 原文链接**

在 `showDetail()` 函数中，在关闭按钮前添加:
```javascript
<a href="https://www.zhipin.com${j.link||''}" target="_blank" style="display:inline-block;margin-top:16px;padding:8px 20px;background:var(--accent);color:white;text-decoration:none;font-size:14px;">查看BOSS直聘原文 →</a>
```

- [ ] **Step 2: 删除 P75/P25 两行**

删除 HTML 模板中第 458-459 行的 P75/P25 行。

- [ ] **Step 3: 重新生成报告验证**

```bash
python tools/analyzer.py data/java后端开发_jobs.json
```

---

### Task 6: scheduler.py — 调度入口

**Files:**
- Create: `scheduler.py`

- [ ] **Step 1: 创建 scheduler.py**

完整代码见下方实现。

- [ ] **Step 2: 端到端验证（使用现有数据模拟）**

```bash
python scheduler.py --dry-run
```
