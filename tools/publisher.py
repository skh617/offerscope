"""BOSS直聘飞书推送 — 组装卡片消息，POST到飞书Webhook"""

import json
import sys
from datetime import datetime
from pathlib import Path

# 尝试导入 requests（飞书推送必需）
try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


def _sign(value):
    """薪资环比符号"""
    if value is None:
        return ""
    if value > 0:
        return f"↑{abs(value)}K"
    elif value < 0:
        return f"↓{abs(value)}K"
    else:
        return "→持平"


def _skill_color(change):
    """技能变化颜色（飞书lark_md标签）"""
    if change is None:
        return ""
    if change > 0.02:
        return "**<font color='green'>"
    elif change < -0.02:
        return "**<font color='red'>"
    else:
        return ""


def _skill_color_end(change):
    if change is not None and abs(change) > 0.02:
        return "</font>**"
    return ""


def build_card(keyword, city, jobs_count, trend_data, report_url=""):
    """组装飞书交互卡片消息

    按需求文档 2.5.1 卡片结构：
    1. 标题栏：关键词+城市+时间戳+样本数
    2. 💰 薪资中位数：当前值+环比涨跌
    3. 🔥 技能热度TOP8：三色区分（涨绿/跌红/持平灰）
    4. 💎 高薪分水岭技能：2-3个
    5. 📈 技能热度变化：上升TOP3（绿）+下降TOP3（红）
    6. 📋 门槛概况：主流经验+主流学历
    7. 📊 详情链接：跳转完整报告

    Args:
        keyword: 搜索关键词
        city: 城市
        jobs_count: 样本数
        trend_data: trend.compare() 的返回结果
        report_url: 完整HTML报告的访问URL

    Returns:
        dict: 飞书消息体
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 1. 标题栏
    title_text = f"{keyword} · {city}  |  {now}  |  {jobs_count}个岗位"

    # 2. 薪资中位数
    med = trend_data.get("salary_median_current", 0)
    med_change = trend_data.get("salary_median_change")
    if med_change is not None:
        salary_line = f"💰 薪资中位数：**{med}K**（环比{_sign(med_change)}）"
    else:
        salary_line = f"💰 薪资中位数：**{med}K**（首次抓取，无环比）"

    # 3. 技能热度 TOP8
    skill_changes = trend_data.get("skill_changes", {})
    top_skills = trend_data.get("top_skills_current", [])
    skill_tags = []
    for s, cnt in top_skills[:8]:
        chg = skill_changes.get(s)
        color = _skill_color(chg)
        color_end = _skill_color_end(chg)
        if color:
            skill_tags.append(f"{color}{s}{color_end}")
        else:
            skill_tags.append(s)
    skill_line = "🔥 技能热度：" + "、".join(skill_tags) if skill_tags else "🔥 技能热度：数据不足"

    # 4. 高薪分水岭技能
    watershed = trend_data.get("watershed_skills", [])
    if watershed:
        ws_line = "💎 高薪分水岭：" + "、".join(f"**{s}**" for s in watershed[:3])
    else:
        ws_line = "💎 高薪分水岭：数据不足"

    # 5. 技能热度变化
    rising = trend_data.get("top_rising", [])
    falling = trend_data.get("top_falling", [])
    change_parts = []
    if rising:
        change_parts.append(
            "📈 上升：" + "、".join(
                f"<font color='green'>{s}(+{c:.0%})</font>" for s, c in rising[:3]
            )
        )
    if falling:
        change_parts.append(
            "📉 下降：" + "、".join(
                f"<font color='red'>{s}({c:.0%})</font>" for s, c in falling[:3]
            )
        )
    change_line = "\n".join(change_parts) if change_parts else "📈 技能变化：无显著变化"

    # 6. 门槛概况 — 从 trend_data 扩展获取（如果没有则标记为待计算）
    exp_main = trend_data.get("main_experience", "")
    edu_main = trend_data.get("main_education", "")
    if exp_main or edu_main:
        threshold_line = f"📋 门槛：{exp_main} · {edu_main}"
    else:
        threshold_line = "📋 门槛：详见完整报告"

    # 7. 详情链接
    if report_url:
        link_line = f"📊 [查看完整报告]({report_url})"
    else:
        link_line = "📊 完整报告已生成"

    # 组装卡片（末尾包含验证关键词 "offer" 以满足飞书安全设置）
    card_body = "\n".join([
        salary_line,
        skill_line,
        ws_line,
        change_line,
        threshold_line,
        link_line,
        "offerscope job market offer",
    ])

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title_text},
                "template": "orange",
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": card_body,
                }
            ],
        },
    }

    return card


def send(card_data, webhook_url):
    """发送飞书消息

    Args:
        card_data: build_card() 返回的消息体
        webhook_url: 飞书机器人 Webhook URL

    Returns:
        bool: 发送是否成功
    """
    if not REQUESTS_OK:
        print("[Publisher] requests 未安装，无法发送飞书消息")
        return False

    if "placeholder" in webhook_url:
        print(f"[Publisher] 跳过发送（placeholder webhook）")
        print(f"[Publisher] 消息内容预览:\n{json.dumps(card_data, ensure_ascii=False, indent=2)}")
        return False

    try:
        resp = requests.post(
            webhook_url,
            json=card_data,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        result = resp.json()
        if result.get("code") == 0:
            print(f"[Publisher] 飞书推送成功: {result.get('msg', 'ok')}")
            return True
        else:
            print(f"[Publisher] 飞书推送失败: {result}")
            return False
    except Exception as e:
        print(f"[Publisher] 飞书推送异常: {e}")
        return False


def push(keyword, city, jobs_count, trend_data, report_url="", webhook_url=""):
    """推送入口：组装并发送

    Args:
        keyword: 关键词
        city: 城市
        jobs_count: 岗位数
        trend_data: 趋势数据
        report_url: 报告链接
        webhook_url: Webhook地址

    Returns:
        bool: 推送是否成功
    """
    card = build_card(keyword, city, jobs_count, trend_data, report_url)
    return send(card, webhook_url)


def dry_run(jobs_file):
    """本地预览推送内容（不实际发送）

    Args:
        jobs_file: JSON岗位数据文件路径
    """
    from tools.trend import compute_trend

    with open(jobs_file, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    kw = jobs[0].get("keyword", "") if jobs else "test"
    city = jobs[0].get("city", "") if jobs else "北京"

    trend = compute_trend(jobs, kw, city)
    card = build_card(kw, city, len(jobs), trend, "http://localhost:8080/report.html")

    print("=" * 60)
    print("  飞书推送预览 (dry-run)")
    print("=" * 60)
    print(f"\n飞书消息体:\n")
    print(json.dumps(card, ensure_ascii=False, indent=2))
    print()
    print("-" * 60)
    print("  卡片内容预览:")
    print("-" * 60)
    md = card["card"]["elements"][0]["content"]
    preview = md.replace("<font color='green'>", "[+]").replace("<font color='red'>", "[-]") \
              .replace("</font>", "").replace("**", "")
    try:
        print(preview)
    except UnicodeEncodeError:
        print(preview.encode('ascii', errors='replace').decode('ascii'))
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tools/publisher.py <jobs.json> [--dry-run]")
        sys.exit(1)

    if "--dry-run" in sys.argv:
        dry_run(sys.argv[1])
    else:
        # 实际推送需要 webhook URL
        print("实际推送请通过 scheduler.py 调用")
        dry_run(sys.argv[1])
