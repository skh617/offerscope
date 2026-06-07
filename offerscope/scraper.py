"""BOSS直聘职位抓取 (CloakBrowser)"""

import json, time, random, re
from pathlib import Path
from cloakbrowser import launch

from offerscope import JOBS_DIR

# ===== 用户参数 =====
KEYWORDS = ["java后端开发"]
CITIES = {"北京": 101010100}
PAGES_PER_SEARCH = 1          # 每个关键词最多滚动轮数（每轮约15条）
MAX_JOBS = 10                 # 最终抓取数量上限
# ====================

OUTPUT_DIR = JOBS_DIR

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

def login_wait(page, on_qr=None):
    """等待用户登录 BOSS 直聘。已登录则直接返回，不触发二维码。"""
    # 先检查是否已有有效登录态
    try:
        page.goto("https://www.zhipin.com/", wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)
        cookies = page.context.cookies()
        has_token = any(c["name"] in ("token", "wt2", "bst") for c in cookies)
        if has_token:
            print("[登录] 已有有效登录态，跳过扫码")
            return True
    except Exception:
        pass

    # 无登录态 → 导航到登录页，获取二维码
    page.goto("https://www.zhipin.com/web/user/?ka=header-login",
              wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    # 截图二维码回传给远程用户
    if on_qr:
        try:
            import base64 as _b64

            # 1. 切换到二维码登录页面
            switch_selectors = [
                "text=微信登录", "text=微信登录/注册", "text=微信注册",
                "text=扫码登录", "text=APP扫码", "text=扫码",
                '[data-type="wechat"]', '[data-type="qrcode"]',
                '.switch-wechat', '.switch-qrcode', '.tab-wechat',
            ]
            for sel in switch_selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        el.click()
                        print(f"[QR] 点击了登录方式切换: {sel}")
                        time.sleep(3)
                        break
                except Exception:
                    continue

            # 2. 尝试获取二维码图片 URL（比截图清晰）
            qr_url = None
            # 先检查 iframe
            iframes = page.query_selector_all("iframe")
            for iframe in iframes:
                try:
                    src = iframe.get_attribute("src")
                    if src and ("qrcode" in src.lower() or "qr" in src.lower()
                                or "weixin" in src.lower() or "wx" in src.lower()
                                or "mp.weixin" in src.lower()):
                        qr_url = src
                        print(f"[QR] 找到 iframe QR: {qr_url[:80]}")
                        break
                except Exception:
                    continue

            # 再检查 img 标签
            if not qr_url:
                img_selectors = [
                    'img[src*="qrcode"]', 'img[src*="QR"]',
                    'img[src*="mp.weixin"]', 'img[src*="open.weixin"]',
                    '.qrcode img', '.qrcode-img img', '.login-qrcode img',
                    '.wechat-qrcode img', 'img[class*="qrcode"]', 'img[class*="qr"]',
                ]
                for sel in img_selectors:
                    try:
                        el = page.query_selector(sel)
                        if el and el.is_visible():
                            qr_url = el.get_attribute("src")
                            if qr_url:
                                print(f"[QR] 找到图片 QR: {qr_url[:80]}")
                                break
                    except Exception:
                        continue

            if qr_url:
                on_qr(f"QR_URL:{qr_url}")
                print("[QR] 二维码 URL 已回传")
            else:
                # 3. 回退：截图
                print("[QR] 未找到 QR URL，使用截图回退")
                img_bytes = page.screenshot(full_page=False, type="png")
                on_qr(f"QR:{_b64.b64encode(img_bytes).decode()}")
                print("[QR] 登录页截图已回传")

        except Exception as e:
            print(f"[QR] 截图失败: {e}")

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

def _safe_print(s):
    """安全打印：处理 Windows GBK 终端无法编码的 Unicode 字符"""
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", errors="replace").decode("ascii"))


def collect_details(page, jobs):
    total = len(jobs)
    consecutive_errors = 0
    for i, job in enumerate(jobs, 1):
        link = job.get("link", "")
        if not link: continue
        _safe_print(f"  [{i}/{total}] {job['name'][:25]}...")
        url = f"https://www.zhipin.com{link}" if link.startswith("/") else link
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(random.uniform(1, 2))
            d = page.evaluate(JS_DETAIL)
            job["salary"] = d.get("salary", "")
            job["description"] = d.get("description", "")
            job["industry"] = d.get("industry", "")
            job["scale"] = d.get("scale", "")
            job["financing"] = d.get("financing", "")
            _safe_print(f"    Salary: {job['salary']}")
            consecutive_errors = 0
            delay(1, 3)
        except Exception as e:
            err = str(e)[:60]
            _safe_print(f"    错误: {err}")
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

# 城市编码映射表
CITY_CODES = {
    "北京": 101010100, "上海": 101020100, "广州": 101280100,
    "深圳": 101280600, "杭州": 101210100, "成都": 101270100,
    "南京": 101190100, "武汉": 101200100, "西安": 101110100,
}


def scrape(keyword, city_name, city_code, max_jobs=40, pages_per_search=2,
           headless=False, on_progress=None, job_id=None):
    """单任务抓取入口 — 供 scheduler / Web 调用

    Args:
        keyword: 搜索关键词
        city_name: 城市中文名（用于数据标记）
        city_code: BOSS直聘城市编码
        max_jobs: 抓取数量上限
        pages_per_search: 滚动翻页轮数
        headless: 是否无头模式（默认 False；Web 部署时可设 True）
        on_progress: 进度回调 fn(msg: str)，Web 调用时传入实时推送进度
        job_id: Web 任务 ID（可选，有则用于文件命名以关联 report）

    Returns:
        (json_path, jobs_list) 或 (None, []) 如果失败
    """
    def _log(msg):
        """同时输出到终端和 Web 进度回调"""
        _safe_print(msg)
        if on_progress:
            on_progress(msg)

    _log(f"[启动] BOSS直聘职位抓取: {keyword} · {city_name}")

    from cloakbrowser import launch_persistent_context
    PROFILE_DIR = Path("boss-profile")
    PROFILE_DIR.mkdir(exist_ok=True)
    context = launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=headless,
        humanize=True,
    )
    page = context.new_page()

    _log("[检查] 正在验证登录状态...")
    # 远程用户需要扫码：把二维码数据通过 on_progress 传出去
    # on_qr 回调直接传带前缀的消息（QR_URL: 或 QR:），不再二次包装
    _qr = (lambda data: on_progress(data)) if on_progress else None
    if not login_wait(page, on_qr=_qr):
        _log("[失败] 登录超时，任务跳过")
        context.close()
        return None, []

    try:
        page.goto("https://www.zhipin.com/", wait_until="domcontentloaded", timeout=60000)
    except Exception:
        time.sleep(5)
    time.sleep(3)

    # 收集列表
    _log(f"[搜索] 正在搜索: {keyword} ...")
    jobs = collect_list(page, keyword, city_name, city_code)
    _log(f"[列表] 采集完成: {len(jobs)} 条")

    # 截断
    if len(jobs) > max_jobs:
        jobs = jobs[:max_jobs]
        _log(f"[截断] 保留前 {max_jobs} 条")

    # 获取详情
    _log(f"[详情] 正在获取岗位详情 (共 {len(jobs)} 条)...")
    collect_details(page, jobs)
    context.close()

    # 保存文件
    from datetime import datetime
    slug = keyword.replace(" ", "_").lower()
    if job_id:
        prefix = f"{slug}_{job_id}"
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
        prefix = f"{slug}_{city_name}_{date_str}"
    save(jobs, prefix)

    filled = sum(1 for j in jobs if j.get("salary"))
    json_path = str(OUTPUT_DIR / f"{prefix}_jobs.json")
    _log(f"[完成] {len(jobs)} 个岗位 | 薪资获取 {filled}/{len(jobs)}")

    return json_path, jobs


def main():
    """独立运行入口 — 使用默认参数批量抓取"""
    import sys
    if len(sys.argv) >= 4:
        # 命令行参数: python scraper.py <keyword> <city> <city_code> [max_jobs]
        kw = sys.argv[1]
        city = sys.argv[2]
        code = int(sys.argv[3])
        max_j = int(sys.argv[4]) if len(sys.argv) > 4 else MAX_JOBS
        scrape(kw, city, code, max_j)
    else:
        # 使用默认配置
        print("=" * 50)
        print("  BOSS直聘职位抓取 (默认配置)")
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
                print(f"  [去重后] +{len(new_jobs)} 条新岗位 (总计 {len(all_jobs)})")
                delay(8, 15)

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
        print(f"  JSON: storage/jobs/{prefix}_jobs.json")
        print(f"{'='*50}")

if __name__ == "__main__":
    main()
