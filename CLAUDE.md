# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# === v2 Web 服务（推荐）===
python web_app.py                           # Start web server (port 8090)
                                            # Open http://localhost:8090

# === v1 CLI 管道 ===
python scheduler.py                         # Full pipeline (scrape → trend → analyze → push)
python scheduler.py --dry-run               # Skip scraping, use existing data

# === 独立工具 ===
python serve.py                             # Legacy report server (port 8092)
python tools/scraper.py <keyword> <city> <city_code> [max_jobs]
python tools/analyzer.py                    # Generates report from newest JSON in data/
python tools/publisher.py <jobs.json> --dry-run  # Preview Feishu card without sending
```

**Environment:** Activate the `.venv` virtual environment before running. Dependencies: `cloakbrowser`, `playwright`, `jieba`, `pyyaml`, `requests`, `fastapi`, `uvicorn`. Node.js >= 18 is required for Playwright. See [doc/init plan.md](doc/init%20plan.md) for Windows-specific setup pitfalls.

## Architecture

The project has two entry points that share the same core modules:

### v2 Web Pipeline (primary)

```
Browser form → [web_app.py]  →  tools/scraper.py   (CloakBrowser → data/*.json)
                              →  tools/analyzer.py   (jieba + Chart.js → reports/*.html)
                              →  tools/publisher.py  (Feishu webhook card)
```

[web_app.py](web_app.py) is a FastAPI app with async job management. Frontend polls `/api/status/{job_id}` every 2s for progress. QR code images are captured server-side and relayed to the frontend.

### v1 CLI Pipeline (legacy)

```
config.yaml  →  scheduler.py  →  tools/scraper.py   (CloakBrowser → data/*.json)
                              →  tools/trend.py      (historical comparison)
                              →  tools/analyzer.py   (jieba + Chart.js → reports/*.html)
                              →  tools/publisher.py  (Feishu webhook card)
```

**Key design: modules are decoupled through JSON files.** Each tool reads/writes JSON in `data/` and can run independently.

| Module | Key exports | Standalone `__main__` |
|--------|------------|----------------------|
| [web_app.py](web_app.py) | FastAPI app (5 routes), `JobState`, `_set_progress()` | `python web_app.py` |
| [tools/scraper.py](tools/scraper.py) | `scrape(keyword, city, code, max_jobs, headless, on_progress)` → `(json_path, jobs_list)` | CLI args |
| [tools/trend.py](tools/trend.py) | `compute_trend(jobs, keyword, city)` → trend dict | No (import-only) |
| [tools/analyzer.py](tools/analyzer.py) | `analyze(jobs)` → HTML string | Finds newest JSON in data/ |
| [tools/publisher.py](tools/publisher.py) | `build_card(...)` + `send(card, webhook)` | `--dry-run` on a JSON file |
| [serve.py](serve.py) | HTTP server (port 8092) with `/report/<slug>` short-link routing | `python serve.py` |

## Configuration

[config.yaml](config.yaml) drives everything:

```yaml
tasks:
  - keyword: AI应用后端工程师
    cities: [北京]
    max_jobs: 10
    webhook: https://open.feishu.cn/open-apis/bot/v2/hook/...
```

The `schedule` and `enabled` fields are reserved for v1.1 but not yet implemented.

## Patterns & Gotchas

### v1 (CLI)

- **City code mapping is duplicated** in both [scheduler.py:189-192](scheduler.py#L189-L192) and [tools/scraper.py](tools/scraper.py#L201-L205). When adding a city, update both places.
- **File naming convention**: `{keyword-slug}_{city}_{date}_jobs.json` in `data/`, `{keyword-slug}_{city}_{date}_分析报告.html` in `reports/`. The slug is `keyword.replace(" ", "_").lower()`.
- **Feishu webhook security**: the card body must contain the word "offer" (the bot's verification keyword). This is appended as the last line of every card in [tools/publisher.py:135-143](tools/publisher.py#L135-L143).
- **Scraper rate limiting**: human-like random delays (3-8s), progressive backoff on consecutive errors (30s → 90s wait). The `max_jobs` parameter controls how many detail pages to fetch.
- **Radar dimensions**: [tools/analyzer.py](tools/analyzer.py) has a 24-dimension candidate pool (`RADAR_CANDIDATES`). Only the 8 most relevant dimensions (by JD keyword match count) appear on the radar chart.
- **Trend module** is import-only — it depends on `tools/analyzer.py` for `extract_salary_range`, `get_top_skills`, and `skill_diff_high_vs_low`. No standalone mode.

### v2 (Web)

- **Scraper new parameters**: `scrape(keyword, city, code, max_jobs=40, pages_per_search=2, headless=False, on_progress=None)`. The `headless` and `on_progress` params are appended at the end for backward compatibility.
- **Persistent browser profile**: `launch_persistent_context(user_data_dir="boss-profile/")` saves cookies/localStorage to disk. Login once, skip QR on subsequent runs. If login breaks, delete the `boss-profile/` directory and re-login.
- **Remote QR code relay flow**: `login_wait(page, on_qr=callback)` → clicks "微信登录" tab → finds QR image URL → sends `QR_URL:<url>` via `on_progress` → `_set_progress()` stores in `JobState.qrcode_url` → frontend renders `<img src="url">`. Fallback: sends `QR:<base64>` screenshot. First non-QR progress message clears the QR fields.
- **GBK-safe printing**: `_safe_print()` wraps `print()` with `UnicodeEncodeError` fallback to ASCII. Use it for any print that may contain job names, salaries, or JD text with special Unicode characters (e.g. `‌` zero-width non-joiner).
- **Concurrency guard**: `_scraping` boolean flag prevents multiple simultaneous scrape jobs (single Chromium instance limitation). Returns HTTP 429 if busy.
- **Job state**: in-memory `dict[job_id] → JobState`. Lost on restart (acceptable for single-machine low-frequency use). No database.
- **Web report naming**: `reports/web_{job_id}.html` (8-char uuid prefix), distinct from v1's `{keyword}_{city}_{date}_分析报告.html`.
- **serve.py is superseded** by web_app.py for v2. `serve.py` remains for v1 CLI backward compatibility.
