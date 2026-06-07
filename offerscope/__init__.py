"""Offerscope — BOSS直聘岗位市场洞察

核心 Python 包，提供：
  - scraper:   BOSS直聘职位抓取 (CloakBrowser)
  - analyzer:  HTML 分析报告生成 (Chart.js + jieba)
  - trend:     历史趋势对比
  - publisher: 飞书卡片推送
  - web:       FastAPI Web 服务
  - cli:       CLI 调度入口
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# 路径常量（全部锚定 __file__，不依赖工作目录）
# ---------------------------------------------------------------------------
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
STORAGE_DIR = PROJECT_DIR / "storage"
JOBS_DIR = STORAGE_DIR / "jobs"
REPORTS_DIR = STORAGE_DIR / "reports"
BROWSER_PROFILE_DIR = PROJECT_DIR / "boss-profile"
TEMPLATES_DIR = PACKAGE_DIR / "templates"

# 确保运行时目录存在
JOBS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
