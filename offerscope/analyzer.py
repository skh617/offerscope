"""BOSS直聘岗位数据分析 — 花叔Design重设计版"""

import json, re, math, os
from collections import Counter
from pathlib import Path

try:
    import jieba
    JIEBA_OK = True
except ImportError:
    JIEBA_OK = False

# ===== 24维候选雷达维度 =====
RADAR_CANDIDATES = [
    ("Python", "python", "django", "flask", "fastapi", "tornado"),
    ("Java/Spring", "java", "spring", "springboot", "mybatis"),
    ("JavaScript/TS", "javascript", "typescript", "node", "vue", "react", "angular"),
    ("C/C++", "c++", "c语言", "cpp"),
    ("机器学习/深度学习", "机器学习", "深度学习", "tensorflow", "pytorch", "nlp"),
    ("大模型/AIGC", "大模型", "aigc", "llm", "gpt", "langchain", "agent"),
    ("云计算/K8s", "docker", "kubernetes", "k8s", "云原生", "devops"),
    ("数据库/SQL", "mysql", "redis", "mongodb", "sql", "数据库", "elasticsearch"),
    ("数据分析", "数据分析", "pandas", "numpy", "spark", "flink"),
    ("前端工程化", "webpack", "vite", "babel", "eslint", "ci/cd"),
    ("移动端", "android", "ios", "flutter", "react native", "小程序"),
    ("测试/自动化", "测试", "自动化测试", "selenium", "pytest"),
    ("网络安全", "安全", "渗透", "加密", "防火墙"),
    ("项目管理", "项目管理", "scrum", "agile", "jira", "需求分析"),
    ("商务谈判", "谈判", "客户", "合同", "商务"),
    ("市场推广", "市场", "推广", "运营", "品牌", "营销", "新媒体"),
    ("财务核算", "财务", "会计", "税务", "审计", "报表"),
    ("法务合规", "法律", "合规", "合规审查", "知识产权"),
    ("人力资源", "招聘", "绩效", "薪酬", "培训", "hr"),
    ("设计/UX", "ui", "ux", "figma", "sketch", "用户体验", "交互"),
    ("算法/数据结构", "算法", "数据结构", "leetcode"),
    ("外语能力", "英语", "日语", "cet-6", "专八"),
    ("AI框架", "rag", "embedding", "vector", "prompt", "fine-tune", "sft", "lora"),
    ("Go/微服务", "golang", "go", "微服务", "grpc", "kafka", "rabbitmq"),
]

SKIP_WORDS = {"熟悉", "了解", "负责", "参与", "相关", "经验", "优先", "以上",
              "岗位", "要求", "工作", "职责", "具备", "能力", "进行", "能够",
              "公司", "团队", "提供", "包括", "一个", "我们", "使用", "开发",
              "设计", "系统", "产品", "技术", "项目", "业务", "数据", "平台",
              "负责", "完成", "需要", "具有", "可以", "以及", "组织", "管理",
              "建设", "优化", "实现", "解决", "支持", "一定", "良好", "较强",
              "合作", "协调", "分析", "提升", "保障", "维护", "跟进", "推动",
              "指导", "建立", "制定", "通过", "配合", "基于", "开展"}

def extract_salary_range(jobs):
    """解析月薪，返回 [(low, high, avg, text), ...]"""
    result = []
    for j in jobs:
        s = j.get("salary", "")
        if not s:
            result.append((0, 0, 0, ""))
            continue
        # 匹配 "20-35K·14薪" 或 "400-500元/天" 格式
        m = re.match(r'(\d+)[-~](\d+)\s*[Kk]', s)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            result.append((lo, hi, (lo + hi) / 2, s))
        else:
            m = re.match(r'(\d+)[-~](\d+)\s*元/天', s)
            if m:
                lo_d, hi_d = int(m.group(1)), int(m.group(2))
                # 日薪转月薪 (21.75天)
                lo, hi = round(lo_d * 21.75 / 1000, 1), round(hi_d * 21.75 / 1000, 1)
                result.append((lo, hi, (lo + hi) / 2, s))
            else:
                m = re.match(r'(\d+)\s*[Kk]', s)
                if m:
                    v = int(m.group(1))
                    result.append((v, v, v, s))
                else:
                    result.append((0, 0, 0, s))
    return result

def classify_jobs(jobs):
    """简单分类：按关键词归类"""
    categories = {}
    for j in jobs:
        kw = j.get("keyword", "其他")
        if kw not in categories:
            categories[kw] = []
        categories[kw].append(j)
    return categories

def extract_keywords(text):
    """用jieba从JD文本提取技能关键词"""
    if not text or not JIEBA_OK:
        return []
    words = jieba.lcut(text)
    # 过滤：长度>=2，非停用词，非纯数字，非纯标点
    result = []
    for w in words:
        w = w.strip().lower()
        if len(w) < 2:
            continue
        if w in SKIP_WORDS:
            continue
        if re.match(r'^[\d\.]+$', w):
            continue
        if re.match(r'^[^\w\u4e00-\u9fff]+$', w):
            continue
        result.append(w)
    return result

def get_top_skills(jobs, n=15):
    """从所有JD中提取TOP N技能词"""
    counter = Counter()
    for j in jobs:
        desc = j.get("description", "")
        kw = extract_keywords(desc)
        counter.update(kw)
    return counter.most_common(n)

def get_radar_scores(jobs, dimensions):
    """计算每个维度的得分（提及该维度关键词的岗位比例）"""
    scores = []
    for dim_name, *keys in dimensions:
        count = 0
        for j in jobs:
            desc = j.get("description", "").lower()
            if any(k in desc for k in keys):
                count += 1
        scores.append(round(count / len(jobs) * 100, 1) if jobs else 0)
    return scores

def select_radar_dims(jobs, n=8):
    """从24候选维度中选n个最相关的"""
    scores = get_radar_scores(jobs, RADAR_CANDIDATES)
    dims_with_scores = list(zip(RADAR_CANDIDATES, scores))
    dims_with_scores.sort(key=lambda x: x[1], reverse=True)
    selected = dims_with_scores[:n]
    return [d[0][0] for d in selected], [d[1] for d in selected]

def salary_histogram(jobs):
    """月度薪资区间柱状图数据"""
    ranges = [
        ("0-10K", 0, 10), ("10-15K", 10, 15), ("15-20K", 15, 20),
        ("20-30K", 20, 30), ("30-40K", 30, 40), ("40-50K", 40, 50),
        ("50K+", 50, 999)
    ]
    salaries = extract_salary_range(jobs)
    counts = []
    for label, lo, hi in ranges:
        cnt = sum(1 for s in salaries if lo <= s[2] < hi)
        counts.append(cnt)
    return [r[0] for r in ranges], counts

def p75_p25(jobs):
    """计算P75和P25月薪阈值"""
    salaries = extract_salary_range(jobs)
    avgs = sorted([s[2] for s in salaries if s[2] > 0])
    if len(avgs) < 4:
        return 0, 0
    p25 = avgs[len(avgs) // 4]
    p75 = avgs[len(avgs) * 3 // 4]
    return p75, p25

def experience_stats(jobs):
    """经验要求分布"""
    counter = Counter()
    for j in jobs:
        exp = j.get("experience", "") or "经验不限"
        if "应届" in exp or "在校" in exp:
            counter["应届生/在校生"] += 1
        elif "1-3" in exp or "1年" in exp:
            counter["1-3年"] += 1
        elif "3-5" in exp:
            counter["3-5年"] += 1
        elif "5-10" in exp:
            counter["5-10年"] += 1
        elif "10" in exp:
            counter["10年以上"] += 1
        else:
            counter["经验不限"] += 1
    return counter

def education_stats(jobs):
    """学历要求分布"""
    counter = Counter()
    for j in jobs:
        edu = j.get("education", "") or "学历不限"
        if "博士" in edu:
            counter["博士"] += 1
        elif "硕士" in edu:
            counter["硕士"] += 1
        elif "本科" in edu:
            counter["本科"] += 1
        elif "大专" in edu or "中专" in edu:
            counter["大专及以下"] += 1
        else:
            counter["学历不限"] += 1
    return counter

def skill_diff_high_vs_low(jobs, top_n=5):
    """高薪vs入门技能差异"""
    salaries = extract_salary_range(jobs)
    p75, p25 = p75_p25(jobs)
    high_jobs = [j for j, s in zip(jobs, salaries) if s[2] >= p75 and p75 > 0]
    low_jobs = [j for j, s in zip(jobs, salaries) if s[2] <= p25 and p25 > 0]
    high_skills = dict(get_top_skills(high_jobs, top_n * 2))
    low_skills = dict(get_top_skills(low_jobs, top_n * 2))
    # 高薪岗位高比例的技能
    high_unique = []
    for sk, cnt in sorted(high_skills.items(), key=lambda x: x[1], reverse=True):
        low_cnt = low_skills.get(sk, 0)
        if cnt > low_cnt * 1.5 and cnt >= 2:
            high_unique.append((sk, cnt))
        if len(high_unique) >= top_n:
            break
    # 入门岗位高比例的技能
    low_unique = []
    for sk, cnt in sorted(low_skills.items(), key=lambda x: x[1], reverse=True):
        high_cnt = high_skills.get(sk, 0)
        if cnt > high_cnt * 1.5 and cnt >= 2:
            low_unique.append((sk, cnt))
        if len(low_unique) >= top_n:
            break
    return high_unique, low_unique

def generate_html(jobs):
    """生成完整HTML报告"""
    categories = classify_jobs(jobs)
    salaries = extract_salary_range(jobs)
    salary_avgs = [s[2] for s in salaries if s[2] > 0]
    median_sal = sorted(salary_avgs)[len(salary_avgs) // 2] if salary_avgs else 0
    top_skills = get_top_skills(jobs)
    p75, p25 = p75_p25(jobs)
    radar_labels, radar_scores = select_radar_dims(jobs)
    sal_labels, sal_counts = salary_histogram(jobs)
    exp_dist = experience_stats(jobs)
    edu_dist = education_stats(jobs)
    high_skills, low_skills = skill_diff_high_vs_low(jobs)

    # Category salary summaries
    cat_summaries = {}
    for cat, cat_jobs in categories.items():
        cat_sal = extract_salary_range(cat_jobs)
        cat_avgs = [s[2] for s in cat_sal if s[2] > 0]
        cat_median = sorted(cat_avgs)[len(cat_avgs)//2] if cat_avgs else 0
        cat_min = min(s[0] for s in cat_sal if s[0] > 0) if cat_avgs else 0
        cat_max = max(s[1] for s in cat_sal if s[1] > 0) if cat_avgs else 0
        # Experience
        cat_exp = Counter()
        for j in cat_jobs:
            e = j.get("experience", "") or "经验不限"
            if "应届" in e or "在校" in e:
                cat_exp["应届生"] += 1
            elif "1-3" in e or "1年" in e:
                cat_exp["1-3年"] += 1
            elif "3-5" in e:
                cat_exp["3-5年"] += 1
            elif "5-10" in e:
                cat_exp["5-10年"] += 1
            elif "10" in e:
                cat_exp["10年+"] += 1
            else:
                cat_exp["不限"] += 1
        main_exp = cat_exp.most_common(1)[0][0] if cat_exp else "不限"
        cat_edu = Counter()
        for j in cat_jobs:
            e = j.get("education", "") or "学历不限"
            if "博士" in e:
                cat_edu["博士"] += 1
            elif "硕士" in e:
                cat_edu["硕士"] += 1
            elif "本科" in e:
                cat_edu["本科"] += 1
            elif "大专" in e or "中专" in e:
                cat_edu["大专及以下"] += 1
            else:
                cat_edu["不限"] += 1
        main_edu = cat_edu.most_common(1)[0][0] if cat_edu else "不限"
        cat_top = get_top_skills(cat_jobs, 5)
        cat_summaries[cat] = {
            "count": len(cat_jobs), "median": cat_median, "min": cat_min, "max": cat_max,
            "exp": main_exp, "edu": main_edu, "skills": [s[0] for s in cat_top]
        }

    # Build HTML
    city = jobs[0].get("city", "") if jobs else ""
    kw = jobs[0].get("keyword", "") if jobs else ""
    title = f"{city}{kw}岗位市场报告" if city and kw else "岗位市场分析报告"

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono&family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@300;400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
:root {{ --bg: #FAF9F6; --accent: #9A3412; --text: #292524; --text-secondary: #78716C;
  --border: #E7E5E4; --card-bg: #FFFFFF; --radius: 4px; --font-serif: 'Noto Serif SC', serif;
  --font-sans: 'Noto Sans SC', sans-serif; --font-mono: 'DM Mono', monospace; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--text); font-family: var(--font-sans); line-height: 1.6; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 0 24px; }}
/* Header */
.report-header {{ padding: 60px 0 40px; border-bottom: 1px solid var(--border); margin-bottom: 48px; }}
.report-header h1 {{ font-family: var(--font-serif); font-size: 36px; font-weight: 700; letter-spacing: 1px; color: var(--accent); margin-bottom: 8px; }}
.report-header .subtitle {{ font-family: var(--font-mono); font-size: 13px; color: var(--text-secondary); letter-spacing: 0.5px; }}
/* Section */
.section {{ margin-bottom: 56px; }}
.section-title {{ font-family: var(--font-serif); font-size: 22px; font-weight: 600; color: var(--accent); margin-bottom: 24px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }}

/* Category Cards */
.cat-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 20px; }}
.cat-card {{ background: var(--card-bg); border: 1px solid var(--border); padding: 24px; }}
.cat-card h3 {{ font-family: var(--font-serif); font-size: 18px; font-weight: 600; margin-bottom: 12px; }}
.cat-card .stat-row {{ display: flex; justify-content: space-between; font-size: 14px; padding: 5px 0; border-bottom: 1px dotted var(--border); }}
.cat-card .stat-label {{ color: var(--text-secondary); }}
.cat-card .stat-value {{ font-family: var(--font-mono); font-weight: 500; }}
.cat-card .skill-tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }}
.skill-tag {{ display: inline-block; padding: 2px 10px; font-size: 12px; background: #FFF7ED; color: var(--accent); border: 1px solid #FED7AA; }}

/* Charts */
.chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
@media (max-width: 768px) {{ .chart-row {{ grid-template-columns: 1fr; }} }}
.chart-box {{ background: var(--card-bg); border: 1px solid var(--border); padding: 20px; }}
.chart-box h4 {{ font-family: var(--font-serif); font-size: 15px; font-weight: 600; margin-bottom: 16px; color: var(--text); }}
.chart-box canvas {{ max-height: 300px; }}

/* Skill bar chart */
.skill-bar-row {{ display: flex; align-items: center; margin-bottom: 8px; font-size: 13px; }}
.skill-bar-label {{ width: 130px; text-align: right; padding-right: 12px; color: var(--text-secondary); flex-shrink: 0; }}
.skill-bar-track {{ flex: 1; height: 20px; background: #F5F5F4; position: relative; }}
.skill-bar-fill {{ height: 100%; background: var(--accent); opacity: 0.8; display: flex; align-items: center; }}
.skill-bar-count {{ font-family: var(--font-mono); font-size: 11px; padding-left: 6px; color: white; }}

/* Diff table */
.diff-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
.diff-col {{ background: var(--card-bg); border: 1px solid var(--border); padding: 20px; }}
.diff-col h4 {{ font-family: var(--font-serif); font-size: 15px; margin-bottom: 12px; }}
.diff-item {{ padding: 6px 0; font-size: 14px; border-bottom: 1px dotted var(--border); display: flex; justify-content: space-between; }}
.diff-item .name {{ font-weight: 500; }}
.diff-item .cnt {{ font-family: var(--font-mono); color: var(--text-secondary); }}

/* Table */
.job-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.job-table th {{ text-align: left; padding: 10px 8px; border-bottom: 2px solid var(--border); font-weight: 600; font-size: 12px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }}
.job-table td {{ padding: 8px; border-bottom: 1px solid var(--border); }}
.job-table tr:hover td {{ background: #FFF7ED; cursor: pointer; }}
.job-table .salary-cell {{ font-family: var(--font-mono); white-space: nowrap; }}

/* Pagination */
.pagination {{ display: flex; justify-content: center; align-items: center; gap: 6px; margin-top: 20px; }}
.page-btn {{ padding: 6px 12px; font-size: 13px; border: 1px solid var(--border); background: var(--card-bg); cursor: pointer; font-family: var(--font-mono); }}
.page-btn:hover {{ background: #FFF7ED; }}
.page-btn.active {{ background: var(--accent); color: white; border-color: var(--accent); }}
.page-btn.disabled {{ opacity: 0.3; cursor: default; }}
.page-ellipsis {{ padding: 6px 4px; font-size: 13px; color: var(--text-secondary); }}

/* Modal */
.modal-overlay {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); z-index: 1000; justify-content: center; align-items: center; }}
.modal-overlay.active {{ display: flex; }}
.modal-content {{ background: var(--bg); max-width: 700px; width: 90%; max-height: 80vh; overflow-y: auto; padding: 32px; border: 1px solid var(--border); }}
.modal-content h3 {{ font-family: var(--font-serif); font-size: 20px; color: var(--accent); margin-bottom: 4px; }}
.modal-meta {{ font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; }}
.modal-meta span {{ margin-right: 16px; }}
.modal-desc {{ font-size: 14px; line-height: 1.8; }}
.modal-desc p {{ margin: 0 0 10px; }}
.modal-desc strong {{ color: #3a2a24; font-size: 15px; }}
.modal-desc .list-num {{ color: var(--accent); font-weight: 600; }}
.modal-close {{ position: absolute; top: 16px; right: 16px; background: none; border: none; font-size: 24px; cursor: pointer; color: var(--text-secondary); }}

/* Market Signals */
.signal-list {{ list-style: none; }}
.signal-list li {{ padding: 8px 0; border-bottom: 1px dotted var(--border); font-size: 14px; }}
.signal-list li::before {{ content: '› '; color: var(--accent); font-weight: bold; }}

/* Footer */
.report-footer {{ margin-top: 60px; padding: 32px 0; border-top: 1px solid var(--border); }}
.report-footer p {{ font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary); text-align: center; }}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<header class="report-header">
  <h1>{title}</h1>
  <p class="subtitle">{len(jobs)} POSITIONS &middot; GENERATED ON {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}</p>
</header>

<!-- JD Summary -->
<section class="section">
  <h2 class="section-title">岗位画像</h2>
  <div class="cat-grid">
'''
    for cat, info in cat_summaries.items():
        tags_html = "".join(f'<span class="skill-tag">{s}</span>' for s in info["skills"][:5])
        html += f'''
    <div class="cat-card">
      <h3>{cat}</h3>
      <div class="stat-row"><span class="stat-label">岗位数</span><span class="stat-value">{info["count"]}</span></div>
      <div class="stat-row"><span class="stat-label">薪资范围</span><span class="stat-value">{info["min"]}-{info["max"]}K</span></div>
      <div class="stat-row"><span class="stat-label">月薪中位数</span><span class="stat-value">{info["median"]:.0f}K</span></div>
      <div class="stat-row"><span class="stat-label">主流经验</span><span class="stat-value">{info["exp"]}</span></div>
      <div class="stat-row"><span class="stat-label">主流学历</span><span class="stat-value">{info["edu"]}</span></div>
      <div class="skill-tags">{tags_html}</div>
    </div>'''

    html += '''
  </div>
</section>

<!-- Radar Chart -->
<section class="section">
  <h2 class="section-title">技能雷达</h2>
  <div class="chart-row">
    <div class="chart-box">
      <h4>全部岗位技能雷达</h4>
      <canvas id="radarChart"></canvas>
    </div>
    <div class="chart-box">
      <h4>技能需求 TOP 15</h4>
      <div style="padding: 0 10px;">
'''

    max_skill_cnt = top_skills[0][1] if top_skills else 1
    for sk, cnt in top_skills[:15]:
        pct = cnt / max_skill_cnt * 100
        html += f'''
        <div class="skill-bar-row">
          <span class="skill-bar-label">{sk}</span>
          <div class="skill-bar-track">
            <div class="skill-bar-fill" style="width:{pct:.0f}%">
              <span class="skill-bar-count">{cnt}</span>
            </div>
          </div>
        </div>'''
    html += '''
      </div>
    </div>
  </div>
</section>

<!-- Salary -->
<section class="section">
  <h2 class="section-title">薪资分析</h2>
  <div class="chart-row">
    <div class="chart-box">
      <h4>月薪区间分布</h4>
      <canvas id="salaryChart"></canvas>
    </div>
    <div class="chart-box">
      <h4>薪资概要</h4>
      <div style="padding: 20px;">
'''
    all_sals_sorted = sorted(salary_avgs)
    med = all_sals_sorted[len(all_sals_sorted)//2] if all_sals_sorted else 0
    avg_sal = sum(salary_avgs)/len(salary_avgs) if salary_avgs else 0
    html += f'''
        <div class="stat-row"><span class="stat-label">月薪中位数</span><span class="stat-value">{med:.1f}K</span></div>
        <div class="stat-row"><span class="stat-label">月薪均值</span><span class="stat-value">{avg_sal:.1f}K</span></div>
        <div class="stat-row"><span class="stat-label">有薪资数据</span><span class="stat-value">{len(salary_avgs)}/{len(jobs)}</span></div>
      </div>
    </div>
  </div>
</section>

<!-- Experience & Education -->
<section class="section">
  <h2 class="section-title">经验与学历</h2>
  <div class="chart-row">
    <div class="chart-box">
      <h4>经验要求分布</h4>
      <canvas id="expChart"></canvas>
    </div>
    <div class="chart-box">
      <h4>学历要求分布</h4>
      <canvas id="eduChart"></canvas>
    </div>
  </div>
</section>

<!-- High vs Entry Skills -->
<section class="section">
  <h2 class="section-title">高薪 vs 入门技能对比</h2>
  <div class="diff-row">
    <div class="diff-col">
      <h4>高薪岗位偏好 (P75+)</h4>
'''
    for sk, cnt in high_skills:
        html += f'<div class="diff-item"><span class="name">{sk}</span><span class="cnt">{cnt}</span></div>'
    if not high_skills:
        html += '<p style="color:var(--text-secondary);font-size:14px;">数据不足，需更多样本</p>'
    html += '''
    </div>
    <div class="diff-col">
      <h4>入门岗位偏好 (P25-)</h4>
'''
    for sk, cnt in low_skills:
        html += f'<div class="diff-item"><span class="name">{sk}</span><span class="cnt">{cnt}</span></div>'
    if not low_skills:
        html += '<p style="color:var(--text-secondary);font-size:14px;">数据不足，需更多样本</p>'
    html += '''
    </div>
  </div>
</section>

<!-- Market Signals -->
<section class="section">
  <h2 class="section-title">市场信号</h2>
  <ul class="signal-list">
'''
    # Generate signals
    if salary_avgs:
        html += f'    <li>月薪中位数 {med:.0f}K，P75/P25 分别为 {p75:.0f}K / {p25:.0f}K</li>\n'
    if top_skills:
        html += f'    <li>最热门技能：{", ".join(s[:] for s,_ in top_skills[:5])}</li>\n'
    exp_main = exp_dist.most_common(1)[0] if exp_dist else ("", 0)
    edu_main = edu_dist.most_common(1)[0] if edu_dist else ("", 0)
    if exp_main[0]:
        html += f'    <li>主流经验要求：{exp_main[0]}（占比 {exp_main[1]/len(jobs)*100:.0f}%）</li>\n'
    if edu_main[0]:
        html += f'    <li>主流学历要求：{edu_main[0]}（占比 {edu_main[1]/len(jobs)*100:.0f}%）</li>\n'
    html += f'    <li>共 {len(categories)} 个搜索方向，涵盖 {len(jobs)} 个岗位</li>\n'
    html += '''
  </ul>
</section>

<!-- Job Table -->
<section class="section">
  <h2 class="section-title">岗位明细</h2>
  <div style="overflow-x:auto;">
  <table class="job-table" id="jobTable">
    <thead><tr>
      <th>#</th><th>岗位名称</th><th>薪资</th><th>经验</th><th>学历</th><th>公司</th><th>城市</th>
    </tr></thead>
    <tbody id="jobTableBody"></tbody>
  </table>
  </div>
  <div class="pagination" id="pagination"></div>
</section>

<!-- Modal -->
<div class="modal-overlay" id="modalOverlay">
  <div class="modal-content" id="modalContent"></div>
</div>

<!-- Footer -->
<footer class="report-footer">
  <p>Generated by BOSS直聘岗位分析 &middot; 花叔Design排版</p>
</footer>

</div>

<script>
// Data
const jobs = ''' + json.dumps(jobs, ensure_ascii=False) + f''';
const PAGE_SIZE = 10;

// Charts
new Chart(document.getElementById('radarChart'), {{
  type: 'radar',
  data: {{
    labels: {json.dumps(radar_labels, ensure_ascii=False)},
    datasets: [{{
      label: '技能提及率 (%)',
      data: {json.dumps(radar_scores)},
      backgroundColor: 'rgba(154,52,18,0.1)',
      borderColor: '#9A3412',
      borderWidth: 1.5,
      pointBackgroundColor: '#9A3412',
      pointRadius: 3,
    }}]
  }},
  options: {{
    responsive: true,
    scales: {{ r: {{ beginAtZero: true, max: 100, ticks: {{ stepSize: 20, font: {{ size: 10 }} }} }} }},
    plugins: {{ legend: {{ display: false }} }}
  }}
}});

new Chart(document.getElementById('salaryChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(sal_labels)},
    datasets: [{{
      data: {json.dumps(sal_counts)},
      backgroundColor: '#C2410C',
      barThickness: 28,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }}
    }}
  }}
}});

new Chart(document.getElementById('expChart'), {{
  type: 'doughnut',
  data: {{
    labels: {json.dumps([k for k,_ in exp_dist.most_common()])},
    datasets: [{{
      data: {json.dumps([v for _,v in exp_dist.most_common()])},
      backgroundColor: ['#C2410C','#EA580C','#F97316','#FB923C','#FDBA74','#FED7AA'],
      borderColor: '#FAF9F6',
      borderWidth: 2,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ font: {{ size: 12 }}, padding: 16 }} }} }}
  }}
}});

new Chart(document.getElementById('eduChart'), {{
  type: 'doughnut',
  data: {{
    labels: {json.dumps([k for k,_ in edu_dist.most_common()])},
    datasets: [{{
      data: {json.dumps([v for _,v in edu_dist.most_common()])},
      backgroundColor: ['#92400E','#B45309','#D97706','#EAB308','#FACC15'],
      borderColor: '#FAF9F6',
      borderWidth: 2,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ font: {{ size: 12 }}, padding: 16 }} }} }}
  }}
}});

// Table pagination
let currentPage = 1;
const totalPages = Math.ceil(jobs.length / PAGE_SIZE);

function renderTable() {{
  const start = (currentPage - 1) * PAGE_SIZE;
  const end = Math.min(start + PAGE_SIZE, jobs.length);
  let html = '';
  for (let i = start; i < end; i++) {{
    const j = jobs[i];
    html += `<tr onclick="showDetail(${{i}})" title="点击查看完整JD">
      <td>${{i+1}}</td><td>${{(j.name||'').substring(0,40)}}</td>
      <td class="salary-cell">${{j.salary||''}}</td>
      <td>${{j.experience||''}}</td><td>${{j.education||''}}</td>
      <td>${{(j.company||'').substring(0,20)}}</td><td>${{j.city||''}}</td>
    </tr>`;
  }}
  document.getElementById('jobTableBody').innerHTML = html;
  renderPagination();
}}

function renderPagination() {{
  let html = '';
  html += `<button class="page-btn ${{currentPage===1?'disabled':''}}" onclick="goPage(${{currentPage-1}})" ${{currentPage===1?'disabled':''}}>&lt;</button>`;
  html += `<button class="page-btn ${{currentPage===1?'active':''}}" onclick="goPage(1)">1</button>`;
  let startP = Math.max(2, currentPage - 2);
  let endP = Math.min(totalPages - 1, currentPage + 2);
  if (startP > 2) html += '<span class="page-ellipsis">...</span>';
  for (let p = startP; p <= endP; p++) {{
    html += `<button class="page-btn ${{p===currentPage?'active':''}}" onclick="goPage(${{p}})">${{p}}</button>`;
  }}
  if (endP < totalPages - 1) html += '<span class="page-ellipsis">...</span>';
  if (totalPages > 1) html += `<button class="page-btn ${{currentPage===totalPages?'active':''}}" onclick="goPage(${{totalPages}})">${{totalPages}}</button>`;
  html += `<button class="page-btn ${{currentPage===totalPages?'disabled':''}}" onclick="goPage(${{currentPage+1}})" ${{currentPage===totalPages?'disabled':''}}>&gt;</button>`;
  document.getElementById('pagination').innerHTML = html;
}}

function goPage(p) {{
  if (p < 1 || p > totalPages) return;
  currentPage = p;
  renderTable();
}}

function showDetail(i) {{
  const j = jobs[i];
  const overlay = document.getElementById('modalOverlay');
  const content = document.getElementById('modalContent');
  content.innerHTML = `
    <h3>${{j.name||''}}</h3>
    <div class="modal-meta">
      <span>${{j.salary||''}}</span><span>${{j.experience||''}}</span><span>${{j.education||''}}</span>
      <span>${{j.company||''}}</span><span>${{j.location||''}}</span>
    </div>
    <div class="modal-meta">
      <span>行业: ${{j.industry||'--'}}</span><span>规模: ${{j.scale||'--'}}</span><span>融资: ${{j.financing||'--'}}</span>
    </div>
    <div class="modal-desc">${{formatDescription(j.description||'暂无描述')}}</div>
    <div style="margin-top:16px;display:flex;gap:12px;">
      <a href="https://www.zhipin.com${{j.link||''}}" target="_blank" style="display:inline-block;padding:8px 20px;background:var(--accent);color:white;text-decoration:none;font-size:14px;">查看BOSS直聘原文 →</a>
      <button style="padding:8px 20px;background:transparent;color:var(--text-secondary);border:1px solid var(--border);cursor:pointer;font-size:14px;" onclick="document.getElementById('modalOverlay').classList.remove('active')">关闭</button>
    </div>
  `;
  overlay.classList.add('active');
}}

document.getElementById('modalOverlay').addEventListener('click', function(e) {{
  if (e.target === this) this.classList.remove('active');
}});
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') document.getElementById('modalOverlay').classList.remove('active');
}});

function formatDescription(text) {{
  // 安全转义 HTML
  text = text.replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // 章节标题加粗
  var headers = ['任职要求', '岗位职责', '职位描述', '岗位要求', '工作内容',
    '技术要求', '能力要求', '加分项', '优先条件',
    '职位要求', '岗位说明', '工作职责', '职责描述'];
  for (var i = 0; i < headers.length; i++) {{
    var h = headers[i];
    text = text.replace(new RegExp(h + '[：:]', 'g'), '<strong>$&</strong>');
  }}

  // 在编号列表项前插入换行（textContent 会丢掉 HTML 换行）
  var NL = String.fromCharCode(10);
  text = text.replace(/([。；;])(\s*)(\d+[.、）)])/g, '$1' + NL + '$3');

  // 双换行分段，单换行转 <br>
  var paras = text.split(new RegExp(NL + '\\s*' + NL));
  return paras.map(function(p) {{
    p = p.trim();
    if (!p) return '';
    // 编号列表项着色
    p = p.replace(new RegExp('^(\\d+)[.、）)]\\\\s*', 'gm'), '<span class="list-num">$1.</span> ');
    return '<p>' + p.replace(new RegExp(NL, 'g'), '<br>') + '</p>';
  }}).join('');
}}

renderTable();
</script>
</body>
</html>'''
    return html

def analyze(jobs):
    """主入口"""
    return generate_html(jobs)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        data_file = Path(sys.argv[1])
    else:
        data_dir = Path("data")
        json_files = sorted(data_dir.glob("*_jobs.json"), key=os.path.getmtime, reverse=True)
        if not json_files:
            print("没有找到数据文件")
            sys.exit(1)
        data_file = json_files[0]
    print(f"分析: {data_file}")
    with open(data_file, "r", encoding="utf-8") as f:
        jobs = json.load(f)
    from offerscope import REPORTS_DIR
    report_dir = REPORTS_DIR
    report_dir.mkdir(exist_ok=True)
    report_name = data_file.stem.replace("_jobs", "") + "_分析报告.html"
    report_path = report_dir / report_name
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(analyze(jobs))
    print(f"报告已生成: {report_path}")
