"""BOSS直聘岗位追踪系统 — 调度入口

读取 config.yaml，遍历任务，串联抓取 → 趋势 → 分析 → 推送流程。
模块通过 JSON 数据文件解耦，单点失败不阻断整体流程。

用法:
    python run_cli.py              # 执行所有任务
    python run_cli.py --dry-run    # 预览模式（跳过实际抓取，用已有数据）
"""

import sys
import json
from pathlib import Path
from datetime import datetime

from offerscope import JOBS_DIR, REPORTS_DIR

# 尝试导入 yaml（配置文件必需）
try:
    import yaml
    YAML_OK = True
except ImportError:
    YAML_OK = False


def load_config(config_path="config.yaml"):
    """加载任务配置"""
    if not YAML_OK:
        print("[错误] PyYAML 未安装，请执行: pip install pyyaml")
        return None

    path = Path(config_path)
    if not path.exists():
        print(f"[错误] 配置文件不存在: {config_path}")
        return None

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config or "tasks" not in config:
        print("[错误] 配置格式无效，缺少 tasks 字段")
        return None

    return config


def run_dry_run(config):
    """预览模式：使用已有数据文件验证流程"""
    print("=" * 60)
    print("  预览模式 (dry-run) — 使用已有数据验证流程")
    print("=" * 60)

    from offerscope.trend import compute_trend
    from offerscope.publisher import build_card

    data_dir = JOBS_DIR
    report_dir = REPORTS_DIR
    report_dir.mkdir(exist_ok=True)

    for task in config["tasks"]:
        keyword = task["keyword"]
        cities = task.get("cities", [])
        webhook = task.get("webhook", "")

        for city in cities:
            print(f"\n{'─'*50}")
            print(f"  任务: {keyword} · {city}")
            print(f"{'─'*50}")

            # 1. 查找已有数据文件
            kw_slug = keyword.replace(" ", "_").lower()
            pattern = f"{kw_slug}_*_jobs.json"
            json_files = sorted(data_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

            if not json_files:
                # 尝试模糊匹配
                json_files = sorted(data_dir.glob(f"{kw_slug}*.json"),
                                   key=lambda p: p.stat().st_mtime, reverse=True)

            if not json_files:
                print(f"  [跳过] 未找到 {keyword} 的数据文件，请先抓取")
                continue

            data_file = json_files[0]
            print(f"  [数据] {data_file}")

            # 2. 加载岗位数据
            with open(data_file, "r", encoding="utf-8") as f:
                jobs = json.load(f)
            print(f"  [样本] {len(jobs)} 个岗位")

            # 3. 趋势分析
            print(f"  [趋势] 计算环比...")
            try:
                trend = compute_trend(jobs, keyword, city)
                if trend["is_first"]:
                    print(f"    → 首次抓取（无历史对比）")
                else:
                    print(f"    → 对比 {trend['history_date']} ({trend['history_count']}条)")
                    if trend["salary_median_change"] is not None:
                        print(f"    → 薪资中位数环比: {trend['salary_median_change']:+.1f}K")
                if trend["top_rising"]:
                    print(f"    → 技能上升: {', '.join(s for s,_ in trend['top_rising'])}")
                if trend["top_falling"]:
                    print(f"    → 技能下降: {', '.join(s for s,_ in trend['top_falling'])}")
                if trend["watershed_skills"]:
                    print(f"    → 分水岭技能: {', '.join(trend['watershed_skills'])}")
            except Exception as e:
                print(f"  [趋势失败] {e}")
                trend = None

            # 4. 生成报告
            print(f"  [报告] 生成 HTML...")
            try:
                from offerscope.analyzer import analyze
                report_name = f"{kw_slug}_{city}_{datetime.now().strftime('%Y-%m-%d')}_分析报告.html"
                report_path = report_dir / report_name
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(analyze(jobs))
                print(f"    → {report_path}")
            except Exception as e:
                print(f"  [报告失败] {e}")
                report_path = None

            # 5. 飞书推送
            print(f"  [推送] 组装卡片...")
            try:
                if trend:
                    slug = "java" if "java" in keyword.lower() else ("ai" if "ai" in keyword.lower() else keyword)
                    report_url = f"http://localhost:8092/report/{slug}" if report_path else ""
                    card = build_card(keyword, city, len(jobs), trend, report_url)
                    print(f"    → 飞书 Webhook: {webhook[:50]}...")

                    # 预览卡片内容
                    md = card["card"]["elements"][0]["content"]
                    preview = md.replace("<font color='green'>", "[+]")
                    preview = preview.replace("<font color='red'>", "[-]")
                    preview = preview.replace("</font>", "")
                    preview = preview.replace("**", "")
                    for line in preview.split("\n"):
                        try:
                            print(f"    {line}")
                        except UnicodeEncodeError:
                            print(f"    {line.encode('ascii', errors='replace').decode('ascii')}")
                else:
                    print(f"    [跳过] 趋势数据不可用")
            except Exception as e:
                print(f"  [推送失败] {e}")

    print(f"\n{'='*60}")
    print(f"  预览完成")
    print(f"{'='*60}")


def run_live(config):
    """实际执行模式：抓取 + 分析 + 推送"""
    print("=" * 60)
    print("  实际执行模式")
    print("=" * 60)

    from offerscope.trend import compute_trend
    from offerscope.publisher import build_card, send
    from offerscope.analyzer import analyze

    data_dir = JOBS_DIR
    report_dir = REPORTS_DIR
    data_dir.mkdir(exist_ok=True)
    report_dir.mkdir(exist_ok=True)

    # 汇总所有抓取任务
    all_tasks = []
    for task in config["tasks"]:
        keyword = task["keyword"]
        max_jobs = task.get("max_jobs", 40)
        for city in task.get("cities", []):
            all_tasks.append((keyword, city, task.get("webhook", ""), max_jobs))

    # 导入 scraper（需要 CloakBrowser 环境）
    try:
        from offerscope.scraper import scrape
        SCRAPER_OK = True
    except ImportError as e:
        print(f"[警告] scraper 导入失败: {e}")
        print("[提示] 将使用已有数据文件（如无数据则跳过）")
        SCRAPER_OK = False

    # 一次浏览器会话完成所有抓取
    if SCRAPER_OK:
        print("\n[抓取] 启动浏览器...")
        # 城市编码映射
        CITY_CODES = {
            "北京": 101010100, "上海": 101020100, "广州": 101280100,
            "深圳": 101280600, "杭州": 101210100, "成都": 101270100,
            "南京": 101190100, "武汉": 101200100, "西安": 101110100,
        }

        for keyword, city, webhook, max_jobs in all_tasks:
            city_code = CITY_CODES.get(city)
            if not city_code:
                print(f"  [跳过] 未知城市编码: {city}")
                continue

            print(f"\n{'─'*50}")
            print(f"  抓取: {keyword} · {city}")
            print(f"{'─'*50}")

            try:
                json_path, jobs = scrape(keyword, city, city_code, max_jobs=max_jobs)
                if json_path and jobs:
                    print(f"  [完成] {len(jobs)} 个岗位 → {json_path}")
                else:
                    print(f"  [失败] 未获取到数据")
                    continue

                # 趋势分析
                trend = compute_trend(jobs, keyword, city)

                # 生成报告
                kw_slug = keyword.replace(" ", "_").lower()
                report_name = f"{kw_slug}_{city}_{datetime.now().strftime('%Y-%m-%d')}_分析报告.html"
                report_path = report_dir / report_name
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(analyze(jobs))
                print(f"  [报告] {report_path}")

                # 推送
                card = build_card(keyword, city, len(jobs), trend, str(report_path))
                send(card, webhook)

            except Exception as e:
                print(f"  [失败] {keyword} · {city}: {e}")
                continue

    else:
        # 无 scraper 时回退到 dry-run
        print("\n[回退] 无抓取能力，执行预览模式...")
        run_dry_run(config)


def main():
    dry_run = "--dry-run" in sys.argv

    config = load_config()
    if not config:
        sys.exit(1)

    print(f"加载配置: {len(config['tasks'])} 个任务")
    for t in config["tasks"]:
        print(f"  - {t['keyword']} → {t['cities']}")

    if dry_run:
        run_dry_run(config)
    else:
        run_live(config)


if __name__ == "__main__":
    main()
