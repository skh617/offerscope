"""BOSS直聘岗位趋势对比 — 读取当前+历史JSON，计算环比变化"""

import json, os, re
from pathlib import Path
from collections import Counter
from datetime import datetime

try:
    import jieba
    JIEBA_OK = True
except ImportError:
    JIEBA_OK = False

# 复用 analyzer 的分析函数
from tools.analyzer import (
    extract_salary_range, get_top_skills, skill_diff_high_vs_low,
)

SKIP_WORDS = {"熟悉", "了解", "负责", "参与", "相关", "经验", "优先", "以上",
              "岗位", "要求", "工作", "职责", "具备", "能力", "进行", "能够",
              "公司", "团队", "提供", "包括", "一个", "我们", "使用", "开发",
              "设计", "系统", "产品", "技术", "项目", "业务", "数据", "平台",
              "负责", "完成", "需要", "具有", "可以", "以及", "组织", "管理",
              "建设", "优化", "实现", "解决", "支持", "一定", "良好", "较强",
              "合作", "协调", "分析", "提升", "保障", "维护", "跟进", "推动",
              "指导", "建立", "制定", "通过", "配合", "基于", "开展"}


def _extract_keywords(text):
    """从文本提取关键词（独立实现，避免循环导入）"""
    if not text or not JIEBA_OK:
        return []
    words = jieba.lcut(text)
    result = []
    for w in words:
        w = w.strip().lower()
        if len(w) < 2:
            continue
        if w in SKIP_WORDS:
            continue
        if re.match(r'^[\d\.]+$', w):
            continue
        if re.match(r'^[^\w一-鿿]+$', w):
            continue
        result.append(w)
    return result


def _skill_mention_rates(jobs):
    """计算每个技能词的提及率（出现该词的岗位数/总岗位数）"""
    if not jobs:
        return {}
    counter = Counter()
    for j in jobs:
        desc = j.get("description", "")
        words = set(_extract_keywords(desc))  # 每个岗位同一词只计一次
        counter.update(words)
    total = len(jobs)
    return {word: count / total for word, count in counter.items()}


def _median_salary(jobs):
    """计算月薪中位数"""
    salaries = extract_salary_range(jobs)
    avgs = sorted([s[2] for s in salaries if s[2] > 0])
    if not avgs:
        return 0
    return avgs[len(avgs) // 2]


def _find_history(keyword, city, data_dir="data"):
    """查找同一关键词+城市的上一次抓取数据
    Returns: (file_path, date_str) or (None, None)
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        return None, None

    # 匹配格式: {keyword}_{city}_{date}_jobs.json
    pattern = re.compile(
        re.escape(keyword.replace(" ", "_").lower()) + r"_.*_(\d{4}-\d{2}-\d{2})_jobs\.json"
    )
    candidates = []
    for f in data_path.glob("*.json"):
        # 从文件名提取城市和日期
        stem = f.stem  # e.g. "java后端开发_北京_2026-06-03_jobs"
        parts = stem.rsplit("_", 2)  # ["java后端开发_北京", "2026-06-03", "jobs"]
        if len(parts) < 3:
            continue
        kw_city = parts[0]  # "java后端开发_北京"
        date_str = parts[1]
        # 检查关键词和城市匹配
        expected_prefix = keyword.replace(" ", "_").lower()
        if kw_city.startswith(expected_prefix) and city in kw_city:
            # 验证日期格式
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                candidates.append((f, date_str))

    if not candidates:
        return None, None

    # 按日期排序，取最近但不是当前的那一个
    candidates.sort(key=lambda x: x[1], reverse=True)
    return str(candidates[0][0]), candidates[0][1]


def compare(current_file, keyword=None, city=None, data_dir="data"):
    """比较当前抓取与历史数据

    Args:
        current_file: 当前JSON文件路径 (str or Path)
        keyword: 关键词（用于查找历史，可选）
        city: 城市（用于查找历史，可选）
        data_dir: 数据目录

    Returns:
        dict: {
            "is_first": bool,
            "current_date": str,
            "history_date": str or None,
            "current_count": int,
            "history_count": int or None,
            "salary_median_current": float,
            "salary_median_history": float or None,
            "salary_median_change": float or None,
            "skill_changes": dict,  # {skill: change_pct}
            "top_rising": [(skill, change_pct), ...],   # TOP3
            "top_falling": [(skill, change_pct), ...],  # TOP3
            "watershed_skills": [skill, ...],           # 高薪分水岭 TOP3
            "top_skills_current": [(skill, count), ...],  # TOP8
        }
    """
    current_file = Path(current_file)
    with open(current_file, "r", encoding="utf-8") as f:
        current_jobs = json.load(f)

    # 提取关键词/城市（如果未提供，从数据推断）
    if keyword is None and current_jobs:
        keyword = current_jobs[0].get("keyword", "")
    if city is None and current_jobs:
        city = current_jobs[0].get("city", "")

    # 当前快照指标
    current_count = len(current_jobs)
    salary_median_current = _median_salary(current_jobs)
    current_rates = _skill_mention_rates(current_jobs)
    current_skills = dict(get_top_skills(current_jobs, 8))
    watershed = skill_diff_high_vs_low(current_jobs, top_n=3)
    watershed_skills = [s[0] for s in watershed[0]] if watershed[0] else []

    # 查找历史数据
    history_file, history_date = _find_history(keyword, city, data_dir)

    result = {
        "is_first": history_file is None,
        "current_date": datetime.now().strftime("%Y-%m-%d"),
        "history_date": history_date,
        "current_count": current_count,
        "history_count": None,
        "salary_median_current": round(salary_median_current, 1),
        "salary_median_history": None,
        "salary_median_change": None,
        "skill_changes": {},
        "top_rising": [],
        "top_falling": [],
        "watershed_skills": watershed_skills[:3],
        "top_skills_current": [(s, c) for s, c in get_top_skills(current_jobs, 8)],
    }

    if history_file is None:
        return result  # 首次抓取，无环比数据

    # 加载历史数据
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history_jobs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return result  # 降级：历史数据不可用

    result["history_count"] = len(history_jobs)
    salary_median_history = _median_salary(history_jobs)
    result["salary_median_history"] = round(salary_median_history, 1)
    result["salary_median_change"] = round(
        salary_median_current - salary_median_history, 1
    )

    # 技能提及率变化
    history_rates = _skill_mention_rates(history_jobs)
    all_skills = set(current_rates.keys()) | set(history_rates.keys())
    skill_changes = {}
    for skill in all_skills:
        cur = current_rates.get(skill, 0)
        hist = history_rates.get(skill, 0)
        change = cur - hist
        # 只保留变化绝对值 > 0.02 或有实际提及的技能
        if abs(change) > 0.02 or cur > 0.05:
            skill_changes[skill] = round(change, 3)

    result["skill_changes"] = skill_changes

    # 上升 TOP3（涨幅最大）
    rising = sorted(
        [(s, c) for s, c in skill_changes.items() if c > 0],
        key=lambda x: x[1], reverse=True
    )
    result["top_rising"] = rising[:3]

    # 下降 TOP3（跌幅最大）
    falling = sorted(
        [(s, c) for s, c in skill_changes.items() if c < 0],
        key=lambda x: x[1]
    )
    result["top_falling"] = falling[:3]

    return result


def compute_trend(jobs, keyword, city, data_dir="data"):
    """从内存中的jobs列表计算趋势（无需存文件）

    Args:
        jobs: 岗位列表
        keyword: 关键词
        city: 城市
        data_dir: 数据目录

    Returns:
        dict: 同 compare() 的返回结构
    """
    current_count = len(jobs)
    salary_median_current = _median_salary(jobs)
    current_rates = _skill_mention_rates(jobs)
    watershed = skill_diff_high_vs_low(jobs, top_n=3)
    watershed_skills = [s[0] for s in watershed[0]] if watershed[0] else []

    # 查找历史数据
    history_file, history_date = _find_history(keyword, city, data_dir)

    result = {
        "is_first": history_file is None,
        "current_date": datetime.now().strftime("%Y-%m-%d"),
        "history_date": history_date,
        "current_count": current_count,
        "history_count": None,
        "salary_median_current": round(salary_median_current, 1),
        "salary_median_history": None,
        "salary_median_change": None,
        "skill_changes": {},
        "top_rising": [],
        "top_falling": [],
        "watershed_skills": watershed_skills[:3],
        "top_skills_current": [(s, c) for s, c in get_top_skills(jobs, 8)],
    }

    if history_file is None:
        return result

    # 加载历史数据
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history_jobs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return result

    result["history_count"] = len(history_jobs)
    salary_median_history = _median_salary(history_jobs)
    result["salary_median_history"] = round(salary_median_history, 1)
    result["salary_median_change"] = round(
        salary_median_current - salary_median_history, 1
    )

    # 技能提及率变化
    history_rates = _skill_mention_rates(history_jobs)
    all_skills = set(current_rates.keys()) | set(history_rates.keys())
    skill_changes = {}
    for skill in all_skills:
        cur = current_rates.get(skill, 0)
        hist = history_rates.get(skill, 0)
        change = cur - hist
        if abs(change) > 0.02 or cur > 0.05:
            skill_changes[skill] = round(change, 3)

    result["skill_changes"] = skill_changes

    rising = sorted(
        [(s, c) for s, c in skill_changes.items() if c > 0],
        key=lambda x: x[1], reverse=True
    )
    result["top_rising"] = rising[:3]

    falling = sorted(
        [(s, c) for s, c in skill_changes.items() if c < 0],
        key=lambda x: x[1]
    )
    result["top_falling"] = falling[:3]

    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    else:
        data_dir = Path("data")
        json_files = sorted(data_dir.glob("*_jobs.json"), key=os.path.getmtime, reverse=True)
        if not json_files:
            print("没有找到数据文件")
            sys.exit(1)
        data_file = str(json_files[0])

    print(f"趋势分析: {data_file}")
    with open(data_file, "r", encoding="utf-8") as f:
        jobs = json.load(f)
    kw = jobs[0].get("keyword", "") if jobs else ""
    city = jobs[0].get("city", "") if jobs else ""

    result = compute_trend(jobs, kw, city)
    print(f"\n{'='*50}")
    print(f"  {kw} · {city} 趋势分析")
    print(f"{'='*50}")
    if result["is_first"]:
        print(f"  状态: 首次抓取（无历史对比数据）")
    else:
        print(f"  历史快照: {result['history_date']} ({result['history_count']}条)")
    print(f"  当前快照: {result['current_date']} ({result['current_count']}条)")
    print(f"  薪资中位数: {result['salary_median_current']}K", end="")
    if result["salary_median_change"] is not None:
        change = result["salary_median_change"]
        arrow = "↑" if change > 0 else ("↓" if change < 0 else "→")
        print(f" (环比{arrow}{abs(change)}K)")
    else:
        print()
    print(f"  高薪分水岭技能: {', '.join(result['watershed_skills']) if result['watershed_skills'] else '数据不足'}")
    if result["top_rising"]:
        print(f"  📈 热度上升: {', '.join(f'{s}(+{c:.0%})' for s,c in result['top_rising'])}")
    if result["top_falling"]:
        print(f"  📉 热度下降: {', '.join(f'{s}({c:.0%})' for s,c in result['top_falling'])}")
    print(f"{'='*50}")
