# 03 — 定时调度

> 状态：设计中 | 优先级：P0（第一优先级第三项） | 依赖：无硬依赖，建议与 [02-task-queue](02-task-queue.md) 共用队列 | 2026-06-07

## 问题

- 目前每次都要手动打开网页 → 填表单 → 点"开始分析"，跟闹钟一样得人盯着
- `config.yaml` 已预留 `schedule` 和 `enabled` 字段但完全是注释，未实现
- 核心价值场景（"每天早上看一眼昨天的市场行情"）无法自动闭环

## 设计

### 依赖

新增依赖 `apscheduler`：

```bash
pip install apscheduler
```

### ① config.yaml 正式启用两个字段

```yaml
tasks:
  - keyword: AI应用后端工程师
    cities: [北京]
    max_jobs: 10
    webhook: https://open.feishu.cn/open-apis/bot/v2/hook/xxx
    schedule: "0 9 * * 1"    # cron：每周一早上9点
    enabled: true             # 开关：可临时禁用某个任务

  - keyword: 全栈
    cities: [北京, 上海]
    max_jobs: 20
    webhook: https://open.feishu.cn/open-apis/bot/v2/hook/yyy
    schedule: "0 9 * * *"    # cron：每天早上9点
    enabled: false
```

**Cron 表达式说明**（APScheduler 标准五字段）：

| 字段 | 范围 | 示例 |
|------|------|------|
| minute | 0–59 | `0` |
| hour | 0–23 | `9` |
| day | 1–31 | `*` |
| month | 1–12 | `*` |
| day_of_week | 0–6 (0=周日) | `1` = 周一 |

### ② web_app.py 启动时加载调度器

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import yaml

_scheduler: BackgroundScheduler = None


def _parse_cron(expr: str):
    """解析 '0 9 * * 1' → CronTrigger 参数"""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron: {expr}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def _start_scheduler():
    """读取 config.yaml，为每个 enabled 任务注册 cron job"""
    global _scheduler

    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    for task in config.get("tasks", []):
        if not task.get("enabled"):
            continue

        schedule_expr = task.get("schedule", "").strip()
        if not schedule_expr:
            continue

        keyword = task["keyword"]
        max_jobs = task.get("max_jobs", 10)
        webhook = task.get("webhook", "")

        for city in task.get("cities", ["北京"]):
            city_code = CITY_CODES.get(city, 101010100)

            _scheduler.add_job(
                _run_scheduled_task,
                trigger=CronTrigger(**_parse_cron(schedule_expr)),
                args=[keyword, city, city_code, max_jobs, webhook],
                id=f"sched-{keyword}-{city}",
                replace_existing=True,
            )
            _safe_print(f"[调度] {keyword} · {city} — {schedule_expr}")

    _scheduler.start()
    _safe_print(f"[调度] 已启动，共注册 {len(_scheduler.get_jobs())} 个定时任务")
```

### ③ `_run_scheduled_task`：无前端交互版抓取流水线

```python
def _run_scheduled_task(keyword: str, city: str, city_code: int,
                        max_jobs: int, webhook: str):
    """调度器回调：独立于 Web 请求，不需要二维码/进度前端"""
    from tools.scraper import scrape
    from tools.analyzer import analyze
    from tools.trend import compute_trend
    from tools.publisher import build_card, send

    _safe_print(f"\n{'='*40}")
    _safe_print(f"[定时任务] {keyword} · {city} 开始")

    json_path, jobs_list = scrape(
        keyword, city, city_code,
        max_jobs=max_jobs,
        headless=True,                              # 无头模式
        profile_dir="boss-profile/_scheduler",       # 专用 Profile
    )

    if not jobs_list:
        _safe_print(f"[定时任务] {keyword} · {city} ❌ 无数据")
        return

    _safe_print(f"[定时任务] {keyword} · {city} 抓取 {len(jobs_list)} 条")

    # 生成报告
    report_html = analyze(jobs_list)
    now = datetime.now()
    report_path = Path(
        f"reports/scheduled_{keyword}_{city}_{now:%Y%m%d_%H%M}.html"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_html, encoding="utf-8")

    # 推送飞书
    if webhook and "open.feishu.cn" in webhook:
        try:
            trend = compute_trend(jobs_list, keyword, city)
            card = build_card(keyword, city, len(jobs_list), trend, report_url="")
            send(card, webhook)
            _safe_print(f"[定时任务] {keyword} · {city} ✅ 已推送")
        except Exception as e:
            _safe_print(f"[定时任务] {keyword} · {city} ⚠️ 推送失败: {e}")
```

### ④ 调度器登录态

调度器使用 `boss-profile/_scheduler/` 专用 Profile，与普通用户的 `boss-profile/{session_id}/` 隔离。

**首次使用需要登录一次：**

- 方案 A（文档指引）：部署者在网页上用 `_scheduler` 作为关键词临时改 session_id 提交一次，扫微信登录后关闭即可
- 方案 B（启动检查）：`web_app.py` 启动时检查 `_scheduler` Profile 是否有有效 cookie，没有则打印提示

> 建议先用方案 A，低成本跑通。方案 B 作为后续优化。

### ⑤ 启动入口

```python
if __name__ == "__main__":
    print("=" * 50)
    print("  Offerscope Web 服务")
    print("  访问: http://localhost:8090")
    print("=" * 50)

    _start_scheduler()   # ← 在 uvicorn.run 之前启动

    uvicorn.run(app, host="0.0.0.0", port=8090)
```

---

## 影响范围

| 文件 | 改动 |
|------|------|
| `config.yaml` | `schedule`/`enabled` 字段正式生效 |
| `web_app.py` | 新增 `_start_scheduler()`、`_run_scheduled_task()`、`_parse_cron()` |
| `requirements.txt` 或 `pyproject.toml` | 新增 `apscheduler` |

---

## 与任务队列的关系

定时任务也应走队列，防止与手动提交的任务冲突。如果 02-task-queue 已实现，**上面的 `_run_scheduled_task` 应替换为：**

```python
def _run_scheduled_task(keyword, city, city_code, max_jobs, webhook):
    """调度器回调：创建 JobState 并入队，复用 _process_queue 消费者"""
    job = JobState(keyword, city, max_jobs, webhook, session_id="_scheduler")
    with _lock:
        if job.job_id in _jobs:
            _jobs[job.job_id] = job
        _queue.append(job)
        if not _processing:
            _processing = True
            threading.Thread(target=_process_queue, daemon=True).start()
```

这样定时任务和手动任务统一排队，不会互相踩踏。`_scheduler` session_id 确保调度器使用 `boss-profile/_scheduler/` 独立 Profile。

---

## 后续扩展

| 扩展 | 说明 |
|------|------|
| API 管理定时任务 | `GET /api/schedules` 列出所有定时任务及下次执行时间；`POST/PUT/DELETE` 动态增删改 |
| 前端展示 | 首页下方显示"下次执行时间"，让用户知道什么时候会自动跑 |
| Profile 有效性检查 | 启动时验证 `_scheduler` Profile 的 cookie 是否过期，提前预警 |
