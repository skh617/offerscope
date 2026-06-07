# 01 — 多用户隔离

> 状态：设计中 | 优先级：P0（第一优先级 | 依赖：无 | 2026-06-07

## 问题

- `tools/scraper.py:313` 硬编码 `PROFILE_DIR = Path("boss-profile")`，所有人共享一个登录态
- `web_app.py:43` 全局一把锁 `_scraping`，一个人用别人就得等
- A 登录微信后，B 来用看到的是 A 的身份——既不合理也不安全

## 设计

三个文件改动，每个文件改动量均在 5–10 行。

### 前端：`templates/index.html`

页面加载时生成 Session ID，存 `localStorage`，每次请求自动带上：

```javascript
// 放在 <script> 顶部，DOMContentLoaded 之前
let sessionId = localStorage.getItem('offerscope_session');
if (!sessionId) {
  sessionId = crypto.randomUUID
    ? crypto.randomUUID().slice(0, 8)
    : Math.random().toString(36).substr(2, 10);
  localStorage.setItem('offerscope_session', sessionId);
}
```

提交时把 `session_id` 放进请求体：

```javascript
// startScrape() 中
body: JSON.stringify({
  keyword, city, max_jobs: parseInt(maxJobs) || 10, webhook,
  session_id: sessionId,   // 新增
}),
```

### 后端：`web_app.py`

**`JobState` 新增字段：**

```python
class JobState:
    def __init__(self, keyword: str, city: str, max_jobs: int,
                 webhook: str, session_id: str):   # 新增参数
        # ... 现有字段 ...
        self.session_id = session_id                # 新增
```

**`/api/scrape` 路由接收 `session_id`：**

```python
session_id = (data.get("session_id") or "default").strip()
# 传给 JobState
job = JobState(keyword, city, max_jobs, webhook, session_id)
```

**`_run_scrape` 传入独立 Profile 目录：**

```python
json_path, jobs_list = scrape(
    job.keyword, job.city, city_code,
    max_jobs=job.max_jobs,
    headless=False,
    on_progress=lambda msg: _set_progress(job, msg),
    profile_dir=f"boss-profile/{job.session_id}",   # 每人独立
)
```

### 爬虫：`tools/scraper.py`

`scrape()` 函数签名新增可选参数，向后兼容：

```python
def scrape(keyword, city_name, city_code, max_jobs=40, pages_per_search=2,
           headless=False, on_progress=None, profile_dir="boss-profile"):
    #                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 新增

    PROFILE_DIR = Path(profile_dir)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)   # parents=True 支持嵌套路径
    context = launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=headless,
        humanize=True,
    )
```

### 并发策略

本次不改。仍然只允许一个抓取任务运行。多用户隔离解决的是**登录态隔离**，同一个 Chromium 实例不同用户排队使用，各自维护独立登录态，互不踢下线。

真正的任务队列在 [02-task-queue.md](02-task-queue.md) 中实现。

---

## 影响范围

| 文件 | 改动类型 | 行数 |
|------|----------|------|
| `templates/index.html` | 新增 session ID 生成 + 提交参数 | ~6 行 |
| `web_app.py` | JobState + api_scrape + _run_scrape | ~8 行 |
| `tools/scraper.py` | scrape() 签名 + profile_dir 参数 | ~4 行 |

全部改动向后兼容，CLI 调用不受影响。

---

## 验证方式

1. 清除浏览器 `localStorage`，刷新页面 → 检查 Application 面板确认生成了新 `offerscope_session`
2. 用浏览器 A 提交任务 → 检查 `boss-profile/{session_a}/` 目录是否创建
3. 用浏览器 B（隐身窗口或另一设备）提交 → 检查 `boss-profile/{session_b}/` 目录，确认与 A 隔离
4. B 请求时 A 还在跑 → 确认返回 429（队列实现前）
