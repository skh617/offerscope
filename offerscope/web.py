"""Offerscope Web 服务 — FastAPI

启动: python run_web.py
访问: http://localhost:8090

路由:
  GET  /                  前端页面
  POST /api/scrape        创建抓取任务
  GET  /api/status/:id    查询任务进度
  GET  /report/:id        查看报告
  GET  /api/reports       最近报告列表
"""

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from offerscope import REPORTS_DIR, TEMPLATES_DIR

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Offerscope", docs_url=None, redoc_url=None)

# ---------------------------------------------------------------------------
# 城市编码（与 scheduler.py 同步）
# ---------------------------------------------------------------------------
CITY_CODES = {
    "北京": 101010100, "上海": 101020100, "广州": 101280100,
    "深圳": 101280600, "杭州": 101210100, "成都": 101270100,
    "南京": 101190100, "武汉": 101200100, "西安": 101110100,
}

# ---------------------------------------------------------------------------
# 任务状态管理（内存）
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_jobs: dict = {}          # job_id → JobState
_scraping = False         # 并发限制：同一时间只允许一个抓取任务


class JobState:
    def __init__(self, keyword: str, city: str, max_jobs: int, webhook: str):
        self.job_id = str(uuid.uuid4())[:8]
        self.keyword = keyword
        self.city = city
        self.max_jobs = max_jobs
        self.webhook = webhook
        self.status = "pending"      # pending | running | done | error
        self.progress = "排队中..."
        self.qrcode = ""             # base64 截图（回退方案）
        self.qrcode_url = ""         # 二维码图片原始 URL（优先使用，更清晰）
        self.jobs_count = 0
        self.report_path = ""
        self.webhook_sent = False
        self.error = ""
        self.created_at = datetime.now().strftime("%m-%d %H:%M")


def _set_progress(job: JobState, msg: str):
    """线程安全的进度更新，自动识别 QR: / QR_URL: 前缀"""
    with _lock:
        if msg.startswith("QR_URL:"):
            job.qrcode_url = msg[7:]
            job.qrcode = ""  # 有 URL 就不用 base64 了
            job.progress = "请使用 BOSS直聘APP 扫描二维码登录"
        elif msg.startswith("QR:"):
            job.qrcode = "data:image/png;base64," + msg[3:]
            job.qrcode_url = ""
            job.progress = "请使用 BOSS直聘APP 扫描二维码登录"
        else:
            job.qrcode = ""
            job.qrcode_url = ""  # 登录完成，清除二维码
            job.progress = msg


# ---------------------------------------------------------------------------
# 后台抓取线程
# ---------------------------------------------------------------------------
def _run_scrape(job: JobState):
    global _scraping
    try:
        with _lock:
            job.status = "running"
        _set_progress(job, "正在启动浏览器...")

        city_code = CITY_CODES.get(job.city, 101010100)

        from offerscope.scraper import scrape

        json_path, jobs_list = scrape(
            job.keyword, job.city, city_code,
            max_jobs=job.max_jobs,
            headless=False,
            on_progress=lambda msg: _set_progress(job, msg),
        )

        if not json_path or not jobs_list:
            with _lock:
                job.status = "error"
                job.error = "抓取失败，未获取到数据"
            return

        with _lock:
            job.jobs_count = len(jobs_list)
        _set_progress(job, "正在生成分析报告...")

        from offerscope.analyzer import analyze
        report_html = analyze(jobs_list)

        report_dir = REPORTS_DIR
        report_dir.mkdir(exist_ok=True)
        report_path = report_dir / f"web_{job.job_id}.html"
        report_path.write_text(report_html, encoding="utf-8")

        with _lock:
            job.report_path = str(report_path)

        # 飞书推送（可选）
        if job.webhook and "open.feishu.cn" in job.webhook:
            _set_progress(job, "正在推送飞书...")
            try:
                from offerscope.trend import compute_trend
                from offerscope.publisher import build_card, send
                trend = compute_trend(jobs_list, job.keyword, job.city)
                card = build_card(
                    job.keyword, job.city, len(jobs_list), trend,
                    report_url="",
                )
                send(card, job.webhook)
                with _lock:
                    job.webhook_sent = True
            except Exception as e:
                _set_progress(job, f"飞书推送失败: {e}")

        with _lock:
            job.status = "done"
            job.progress = "✅ 报告已生成"
        _set_progress(job, "✅ 报告已生成")

    except Exception as e:
        with _lock:
            job.status = "error"
            job.error = str(e)
    finally:
        _scraping = False


# ---------------------------------------------------------------------------
# 读取前端模板
# ---------------------------------------------------------------------------
_TEMPLATE_PATH = TEMPLATES_DIR / "index.html"
if _TEMPLATE_PATH.exists():
    INDEX_HTML = _TEMPLATE_PATH.read_text(encoding="utf-8")
else:
    INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>Offerscope</title></head>
<body><h1>Offerscope</h1><p>模板文件未找到: templates/index.html</p></body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML


@app.post("/api/scrape")
async def api_scrape(request: Request):
    global _scraping

    if _scraping:
        return JSONResponse({"error": "已有任务正在执行，请稍后再试"}, status_code=429)

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "请求格式错误"}, status_code=400)

    keyword = (data.get("keyword") or "").strip()
    if not keyword:
        return JSONResponse({"error": "请输入岗位名称"}, status_code=400)

    city = (data.get("city") or "北京").strip()
    if city not in CITY_CODES:
        return JSONResponse({"error": f"不支持的城市: {city}"}, status_code=400)

    try:
        max_jobs = int(data.get("max_jobs", 10))
    except (TypeError, ValueError):
        max_jobs = 10
    max_jobs = max(1, min(max_jobs, 50))

    webhook = (data.get("webhook") or "").strip()
    if webhook and not webhook.startswith("https://open.feishu.cn/"):
        return JSONResponse({"error": "飞书 Webhook 地址格式不正确"}, status_code=400)

    with _lock:
        _scraping = True

    job = JobState(keyword, city, max_jobs, webhook)
    with _lock:
        _jobs[job.job_id] = job

    thread = threading.Thread(target=_run_scrape, args=(job,), daemon=True)
    thread.start()

    return {"job_id": job.job_id, "status": "pending"}


@app.get("/api/status/{job_id}")
async def api_status(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "qrcode": job.qrcode or None,
        "qrcode_url": job.qrcode_url or None,
        "keyword": job.keyword,
        "city": job.city,
        "jobs_count": job.jobs_count,
        "webhook_sent": job.webhook_sent,
        "error": job.error,
        "report_url": f"/report/{job_id}" if job.status == "done" else None,
    }


@app.get("/report/{job_id}", response_class=HTMLResponse)
async def view_report(job_id: str):
    report_path = REPORTS_DIR / f"web_{job_id}.html"
    if not report_path.exists():
        raise HTTPException(404, "报告不存在或已被清理")
    return report_path.read_text(encoding="utf-8")


@app.get("/api/reports")
async def api_reports():
    """返回最近报告列表（扫描 reports/ 目录）"""
    report_dir = REPORTS_DIR
    if not report_dir.exists():
        return {"reports": []}

    reports = []
    for f in sorted(report_dir.glob("web_*.html"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
        reports.append({
            "job_id": f.stem.replace("web_", ""),
            "name": f.stem,
            "time": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            "url": f"/report/{f.stem.replace('web_', '')}",
        })

    return {"reports": reports}


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
def main():
    """启动 Web 服务（供 run_web.py 调用）"""
    print("=" * 50)
    print("  Offerscope Web 服务")
    print("  访问: http://localhost:8090")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8090)


if __name__ == "__main__":
    main()
