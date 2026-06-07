# 02 — 任务队列

> 状态：设计中 | 优先级：P0（紧跟多用户隔离） | 依赖：[01-multi-user-isolation](01-multi-user-isolation.md) | 2026-06-07

## 问题

- `web_app.py:43` `_scraping = False` 是布尔锁，有人在抓就返回 HTTP 429
- 用户只能反复重试，体验差
- 尤其是定时调度上线后，可能在无人值守时与手动任务冲突

## 设计

### 核心思路

把 `_scraping: bool` 替换为 `_queue: deque` + `_processing: bool`。不到 30 行改动。

无需常驻后台线程——只在有新任务且当前空闲时才起线程，执行完队列后线程自然退出。

### 后端：`web_app.py`

```python
from collections import deque

_queue: deque[JobState] = deque()   # 待执行任务队列
_processing = False                  # 是否有任务正在执行


def _process_queue():
    """消费者：从队列头部取出任务依次执行"""
    global _processing
    while _queue:
        job = _queue.popleft()
        _run_scrape(job)
    _processing = False


@app.post("/api/scrape")
async def api_scrape(request: Request):
    # ... 参数校验（不变）...

    job = JobState(keyword, city, max_jobs, webhook, session_id)
    with _lock:
        _jobs[job.job_id] = job

        # 去重：同 session_id 已有任务在排队/执行中
        for j in _queue:
            if j.session_id == job.session_id:
                return {
                    "job_id": j.job_id,
                    "status": j.status,
                    "duplicate": True,
                }

        queue_pos = len(_queue)
        _queue.append(job)

        if queue_pos == 0 and not _processing:
            _processing = True
            threading.Thread(target=_process_queue, daemon=True).start()

    return {
        "job_id": job.job_id,
        "status": "pending",
        "queue_position": queue_pos,
    }
```

### `/api/status/{job_id}` 新增返回值

```python
return {
    # ... 现有字段 ...
    "queue_position": _get_queue_position(job_id),   # 0 表示正在执行
}
```

### 前端：`templates/index.html`

排队时显示友好提示：

```javascript
// pollStatus() 中
if (data.queue_position && data.queue_position > 0 && data.status === 'pending') {
  document.getElementById('progress-msg').textContent =
    `排队中... 前面还有 ${data.queue_position} 个任务`;
  // 不显示二维码区域
  document.getElementById('qrcode-area').style.display = 'none';
  return;
}
```

### 去重策略

同一个 Session ID 重复提交：不排队，不拒绝，直接返回已有任务的状态和 job_id。前端拿到 `duplicate: true` 后自动轮询那个 job_id。

这样用户不小心点了两次"开始分析"，不会产生两个任务。

---

## 状态流转

```
POST /api/scrape
  │
  ├─ 同 session 已有任务 → 返回已有 job_id（duplicate: true）
  │
  └─ 新任务 → 加入队列尾部
       │
       ├─ 队列为空 + 无正在执行 → 即刻启动消费者线程
       └─ 队列非空 → 排队等待
            │
            ▼
       _process_queue()
            │
            ├─ popleft() → _run_scrape(job) → done/error
            ├─ 队列还有 → 继续下一个
            └─ 队列空 → _processing = False, 线程退出
```

---

## 影响范围

| 文件 | 改动 |
|------|------|
| `web_app.py` | 全局变量替换（`_scraping` → `_queue`/`_processing`） |
| `web_app.py` | 新增 `_process_queue()` 函数 |
| `web_app.py` | `api_scrape` 改为入队逻辑 + 去重 |
| `web_app.py` | `api_status` 新增 `queue_position` |
| `templates/index.html` | 前端处理排队状态显示 |

---

## 边界情况

| 场景 | 处理 |
|------|------|
| 消费者线程崩溃 | 单个任务 `_run_scrape` 内有 try/except，异常只影响当前任务，队列继续 |
| 队列中有多个任务时服务重启 | 内存队列丢失，可接受（单机低频场景） |
| 定时任务与手动任务冲突 | 共用同一队列，谁先到谁先执行 |
