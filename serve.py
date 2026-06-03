"""本地报告 HTTP 服务 — 托管 reports/ 目录，ASCII 短链接避免中文URL编码问题"""

import http.server
import socketserver
import shutil
from pathlib import Path
from urllib.parse import unquote

PORT = 8092
REPORT_DIR = Path(__file__).parent / "reports"

# 关键词 → 英文短名映射
SLUG_MAP = {
    "ai": ["ai应用开发", "AI应用开发"],
    "java": ["java后端开发", "Java后端开发"],
}


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def _find_report(slug):
    """根据短名找最新的报告文件"""
    keywords = SLUG_MAP.get(slug, [slug])
    candidates = []
    for f in REPORT_DIR.glob("*.html"):
        stem = f.stem.lower()
        for kw in keywords:
            if kw.lower() in stem:
                candidates.append((f, f.stat().st_mtime))
                break
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPORT_DIR), **kwargs)

    def do_GET(self):
        # URL 解码（处理浏览器自动编码的中文）
        path = unquote(self.path)

        # 短名路由: /report/ai → 最新 AI 报告
        if path.startswith("/report/"):
            slug = path.split("/report/")[1].split("?")[0].strip()
            target = _find_report(slug)
            if target:
                self.path = f"/{target.name}"
            else:
                self.send_error(404, f"Report not found: {slug}")
                return

        return super().do_GET()

    def log_message(self, format, *args):
        print(f"  [{self.client_address[0]}] {args[0]}")


def main():
    if not REPORT_DIR.exists():
        REPORT_DIR.mkdir(parents=True)

    with ReusableTCPServer(("", PORT), Handler) as httpd:
        print(f"报告服务: http://localhost:{PORT}")
        print()
        print("快捷链接（复制到浏览器）:")
        print(f"  AI应用开发   → http://localhost:{PORT}/report/ai")
        print(f"  Java后端开发 → http://localhost:{PORT}/report/java")
        print()
        # 列出已有文件，也支持直接访问
        reports = sorted(REPORT_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        if reports:
            print("已有报告:")
            for r in reports[:10]:
                print(f"  {r.name}")
        print()
        print("按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止")


if __name__ == "__main__":
    main()
