"""BOSS直聘职位抓取 (CloakBrowser)"""

import json, csv, time, random, re
from pathlib import Path
from cloakbrowser import launch

# ===== 用户参数 =====
KEYWORDS = ["java后端开发"]
CITIES = {"北京": 101010100}
PAGES_PER_SEARCH = 1          # 每个关键词最多滚动轮数（每轮约15条）
MAX_JOBS = 10                 # 最终抓取数量上限
# ====================

OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)

JS_LIST = """
() => {
    const cards = document.querySelectorAll('li.job-card-box');
    return Array.from(cards).map(card => {
        const name = card.querySelector('.job-name');
        const tags = card.querySelectorAll('.tag-list li');
        const company = card.querySelector('.boss-name');
        const location = card.querySelector('.company-location');
        const tagTexts = Array.from(tags).map(t => t.textContent.trim());
        let experience = '', education = '';
        for (const t of tagTexts) {
            if (t.includes('年') || t === '应届生' || t === '在校生' || t.includes('经验'))
                experience = t;
            else if (['本科','硕士','博士','大专','学历不限','中专/中技','高中'].some(k => t.includes(k)))
                education = t;
        }
        return {
            name: name ? name.textContent.trim() : '',
            link: name ? name.getAttribute('href') : '',
            experience, education,
            company: company ? company.textContent.trim() : '',
            location: location ? location.textContent.trim() : '',
        };
    }).filter(j => j.name);
}
"""

JS_DETAIL = """
() => {
    const r = {};
    const sal = document.querySelector('.salary, .info-primary .salary');
    r.salary = sal ? sal.textContent.trim() : '';
    const desc = document.querySelector('.job-sec-text, .job-detail-section .text, .text.fold-text');
    r.description = desc ? desc.textContent.trim() : '';
    const ct = Array.from(document.querySelectorAll('.sider-company-info li, .company-info li'))
        .map(t => t.textContent.trim()).filter(Boolean);
    r.industry = ''; r.scale = ''; r.financing = '';
    for (const t of ct) {
        if (t.match(/\\d+.*人/) || t.includes('以上') || t.includes('少于')) r.scale = t;
        else if (t.includes('融资') || t.includes('上市') || t.includes('不需要融资')) r.financing = t;
        else if (t.length > 1 && t.length < 20) r.industry = r.industry || t;
    }
    return r;
}
"""

def delay(a=3, b=7):
    time.sleep(random.uniform(a, b))

def wait_jobs(page, sec=25):
    for _ in range(sec):
        time.sleep(1)
        try:
            if page.evaluate("document.querySelectorAll('li.job-card-box').length") > 0:
                return True
        except: pass
    return False

def login_wait(page):
    page.goto("https://www.zhipin.com/web/user/?ka=header-login",
              wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    print("[等待登录] 请在浏览器中登录BOSS直聘...")
    for i in range(36):
        time.sleep(5)
        try:
            cookies = page.context.cookies()
            has_token = any(c["name"] in ("token","wt2","bst") for c in cookies)
            url = page.url
            if has_token or ("user" not in url and "login" not in url):
                print(f"[登录成功]")
                return True
            print(f"  [{i+1}/36] 等待中...", end="\r")
        except: pass
    print("[超时] 未检测到登录")
    return False

def wait_new_cards(page, old_count, timeout=8):
    """等待页面卡片数量超过 old_count，最多等 timeout 秒"""
    for _ in range(timeout * 2):
        time.sleep(0.5)
        try:
            n = page.evaluate("document.querySelectorAll('li.job-card-box').length")
            if n > old_count:
                return n
        except:
            pass
    return old_count

def collect_list(page, keyword, city_name, city_code):
    """通过触底滚动加载抓取列表页，最多滚动 PAGES_PER_SEARCH 轮"""
    url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}"
    print(f"  [加载首页] {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        print(f"  [导航错误] {e}")
        return []
    if not wait_jobs(page):
        print(f"  [无结果]")
        return []

    # 先采集首屏已有的卡片
    time.sleep(2)
    jobs = []
    batch = page.evaluate(JS_LIST)
    for j in batch:
        j["keyword"] = keyword
        j["city"] = city_name
    jobs.extend(batch)
    print(f"  [首屏] {len(jobs)} 条")

    # 滚动加载更多
    no_new_count = 0
    for round_i in range(1, PAGES_PER_SEARCH + 1):
        old_count = page.evaluate("document.querySelectorAll('li.job-card-box').length")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        new_count = wait_new_cards(page, old_count)

        batch = page.evaluate(JS_LIST)
        existing = {j["link"] for j in jobs}
        new = [j for j in batch if j["link"] not in existing]
        for j in new:
            j["keyword"] = keyword
            j["city"] = city_name
        jobs.extend(new)
        print(f"  [第{round_i}轮滚动] 卡片 {old_count}→{new_count}, +{len(new)} 条新 (累计 {len(jobs)})")

        if len(new) == 0:
            no_new_count += 1
            if no_new_count >= 2:
                print(f"  [连续{no_new_count}轮无新数据，停止]")
                break
        else:
            no_new_count = 0
        delay(2, 4)
    return jobs

def collect_details(page, jobs):
    total = len(jobs)
    consecutive_errors = 0
    for i, job in enumerate(jobs, 1):
        link = job.get("link", "")
        if not link: continue
        print(f"  [{i}/{total}] {job['name'][:25]}...", end=" ", flush=True)
        url = f"https://www.zhipin.com{link}" if link.startswith("/") else link
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(random.uniform(1, 2))
            d = page.evaluate(JS_DETAIL)
            job["salary"] = d.get("salary", "")
            job["description"] = d.get("description", "")[:500]
            job["industry"] = d.get("industry", "")
            job["scale"] = d.get("scale", "")
            job["financing"] = d.get("financing", "")
            print(f"{job['salary']}")
            consecutive_errors = 0
            delay(1, 3)
        except Exception as e:
            err = str(e)[:60]
            print(f"错误: {err}")
            consecutive_errors += 1
            if consecutive_errors >= 3 or "DISCONNECTED" in err.upper():
                wait = min(30 + consecutive_errors * 10, 90)
                print(f"  [限流/连续错误] 等待{wait}秒...")
                time.sleep(wait)
                try:
                    page.goto("https://www.zhipin.com/", wait_until="domcontentloaded", timeout=20000)
                    time.sleep(3)
                except: pass
            else:
                delay(2, 4)

def save(jobs, prefix):
    with open(OUTPUT_DIR / f"{prefix}_jobs.json", "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    fields = ["keyword","city","name","salary","experience","education",
              "company","location","industry","scale","financing","description","link"]
    with open(OUTPUT_DIR / f"{prefix}_jobs.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(jobs)

def main():
    print("=" * 50)
    print("  BOSS直聘职位抓取")
    print(f"  关键词: {KEYWORDS}")
    print(f"  城市: {list(CITIES.keys())}")
    print(f"  上限: {MAX_JOBS} 条")
    print("=" * 50)
    browser = launch(headless=False, humanize=True)
    page = browser.new_page()
    login_wait(page)
    try:
        page.goto("https://www.zhipin.com/", wait_until="domcontentloaded", timeout=60000)
    except Exception:
        time.sleep(5)
    time.sleep(3)
    all_jobs = []
    seen_links = set()
    for kw in KEYWORDS:
        if len(all_jobs) >= MAX_JOBS:
            print(f"\n[已达上限 {MAX_JOBS}，停止列表采集]")
            break
        for city, code in CITIES.items():
            if len(all_jobs) >= MAX_JOBS:
                break
            print(f"\n--- {kw} | {city} ---")
            jobs = collect_list(page, kw, city, code)
            new_jobs = [j for j in jobs if j["link"] not in seen_links]
            for j in new_jobs:
                seen_links.add(j["link"])
            all_jobs.extend(new_jobs)
            need = MAX_JOBS - len(all_jobs) + len(new_jobs)
            print(f"  [去重后] +{len(new_jobs)} 条新岗位 (总计 {len(all_jobs)})")
            delay(8, 15)

    # 截断到 MAX_JOBS
    if len(all_jobs) > MAX_JOBS:
        all_jobs = all_jobs[:MAX_JOBS]
        print(f"\n[截断] 保留前 {MAX_JOBS} 条")

    prefix = KEYWORDS[0].replace(" ","_").lower()
    save(all_jobs, prefix)
    print(f"\n[列表完成] {len(all_jobs)} 条（去重后），开始获取详情...")
    collect_details(page, all_jobs)
    browser.close()
    save(all_jobs, prefix)
    filled = sum(1 for j in all_jobs if j.get("salary"))
    print(f"\n{'='*50}")
    print(f"  完成! {len(all_jobs)} 个岗位 | 薪资获取 {filled}/{len(all_jobs)}")
    print(f"  CSV: data/{prefix}_jobs.csv")
    print(f"  JSON: data/{prefix}_jobs.json")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
