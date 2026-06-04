# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Full pipeline (scrape → trend → analyze → push to Feishu)
python scheduler.py

# Dry-run: skip scraping, use existing data files to generate report + preview push
python scheduler.py --dry-run

# Start local HTTP server to host reports (port 8092)
python serve.py

# Run individual tools standalone
python tools/scraper.py <keyword> <city> <city_code> [max_jobs]
python tools/analyzer.py                    # generates report from newest JSON in data/
python tools/publisher.py <jobs.json> --dry-run  # preview Feishu card without sending
```

**Environment:** Activate the `.venv` virtual environment before running. Dependencies are installed ad-hoc (no `requirements.txt`): `cloakbrowser`, `playwright`, `jieba`, `pyyaml`, `requests`. Node.js >= 18 is required for Playwright. See [doc/init plan.md](doc/init%20plan.md) for Windows-specific setup pitfalls.

## Architecture

The project follows a **pipeline pattern** orchestrated by [scheduler.py](scheduler.py):

```
config.yaml  →  scheduler.py  →  tools/scraper.py   (CloakBrowser → data/*.json)
                              →  tools/trend.py      (historical comparison)
                              →  tools/analyzer.py   (jieba + Chart.js → reports/*.html)
                              →  tools/publisher.py  (Feishu webhook card)
```

**Key design: modules are decoupled through JSON files.** Each tool reads/writes JSON in `data/` and can run independently. This means `--dry-run` works without the scraper, and trend/analyze/publish can be iterated on without re-scraping.

| Module | Key exports | Standalone `__main__` |
|--------|------------|----------------------|
| [tools/scraper.py](tools/scraper.py) | `scrape(keyword, city, code, max_jobs)` → `(json_path, jobs_list)` | CLI args |
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

- **City code mapping is duplicated** in both [scheduler.py:189-192](scheduler.py#L189-L192) and [tools/scraper.py](tools/scraper.py#L201-L205). When adding a city, update both places.
- **File naming convention**: `{keyword-slug}_{city}_{date}_jobs.json` in `data/`, `{keyword-slug}_{city}_{date}_分析报告.html` in `reports/`. The slug is `keyword.replace(" ", "_").lower()`.
- **Feishu webhook security**: the card body must contain the word "offer" (the bot's verification keyword). This is appended as the last line of every card in [tools/publisher.py:135-143](tools/publisher.py#L135-L143).
- **CloakBrowser session**: cookies and localStorage are persisted so BOSS Zhipin login survives across runs. If scraping fails with redirects, the session may have expired — delete browser profile data and re-login.
- **Scraper rate limiting**: human-like random delays (3-8s), progressive backoff on consecutive errors (30s → 90s wait). The `max_jobs` parameter controls how many detail pages to fetch.
- **Radar dimensions**: [tools/analyzer.py](tools/analyzer.py) has a 24-dimension candidate pool (`RADAR_CANDIDATES`). Only the 8 most relevant dimensions (by JD keyword match count) appear on the radar chart.
- **serve.py slug map**: [serve.py:13-16](serve.py#L13-L16) maps short ASCII names to report filename patterns. Add new entries when adding keywords to avoid Chinese URL encoding in Feishu links.
- **Trend module** is import-only — it depends on `tools/analyzer.py` for `extract_salary_range`, `get_top_skills`, and `skill_diff_high_vs_low`. No standalone mode.
