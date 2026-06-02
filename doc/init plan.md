# BOSS直聘抓取环境配置 — 执行计划

## Context

用户需要在 Windows 10 环境下配置 BOSS直聘抓取环境，为后续 `boss-scrape`（抓取）和 `boss-analyze`（分析）做准备。

**输入源：**
- `D:\AI Projects\offerscope\doc\QUICK_START.md` — 官方 Quick Start 文档
- `C:\Users\97052\.claude\skills\boss-setup\SKILL.md` — boss-setup skill 的 5 步流程

## 关键适配：Windows 平台

Skill 中的路径为 Linux 风格，在 Windows (bash/Git Bash) 下需调整为：

| Skill 原命令 | Windows 调整 |
|---|---|
| `source .venv/bin/activate` | `source .venv/Scripts/activate` |
| `python3` | `python` |

## 踩坑记录（重要！）

以下是实际运行中遇到的坑及解决方案，**必须严格按照解决方案操作**，否则无法一遍通过。

### 坑1: pip 版本过旧导致包安装失败

**现象**：pip 23.2.1 下载 jieba 时报 hash mismatch 错误，重试多次每次 hash 都不同（下载中断/网络不稳）。

**解决方案**：
1. 升级 pip：`python -m pip install --upgrade pip`
2. 所有 `pip install` 命令使用清华镜像源加速：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <package>`
3. 加上 `--no-cache-dir` 避免缓存脏数据

### 坑2: Playwright Chromium 下载被 kill（exit 137）

**现象**：`playwright install chromium` 下载约 112MB 的 Chrome Headless Shell，因 CDN 速度慢（~30KB/s），在 bash 中反复超时被 kill（exit 137）。

**根本原因**：Playwright v1.60 需要的是 `chromium_headless_shell-1223`（Chrome Headless Shell），不是旧的 `chromium-1223`（完整 Chromium）。若 `ms-playwright` 目录已有旧版 chromium，不会生效。

**解决方案——手动下载 + 解压**：
1. 获取下载 URL：运行 `python -m playwright install chromium` 被 kill 时，从输出中复制 zip 下载链接（形如 `https://cdn.playwright.dev/builds/cft/<version>/win64/chrome-headless-shell-win64.zip`）
2. 用浏览器或下载工具下载 zip 文件（约 112MB）
3. 手动解压到 Playwright 缓存目录：
   ```bash
   mkdir -p "$HOME/AppData/Local/ms-playwright/chromium_headless_shell-1223"
   cd "$HOME/AppData/Local/ms-playwright/chromium_headless_shell-1223"
   unzip -o /path/to/chrome-headless-shell-win64.zip
   touch INSTALLATION_COMPLETE
   ```
4. 验证：解压后必须有 `chrome-headless-shell-win64/chrome-headless-shell.exe`

### 坑3: Playwright 锁文件残留

**现象**：Playwright 安装被 kill 后，目录下残留 `__dirlock` 文件夹，后续安装直接报错 "An active lockfile is found"。

**解决方案**：
```bash
rm -rf "$HOME/AppData/Local/ms-playwright/__dirlock"
```

### 坑4: Bash 嵌套引号导致 Python -c 执行失败（exit 127）

**现象**：`python -c "..."` 命令中包含嵌套的单引号/双引号时，bash 解析错误，报 `No such file or directory`。

**解决方案**：不要直接在 bash 中使用带复杂引号的 `python -c`。改为先将 Python 代码写入临时文件，再运行：
```bash
cat > _temp_script.py << 'PYEOF'
...python code...
PYEOF
python _temp_script.py
rm _temp_script.py
```

### 坑5: CloakBrowser 首次运行自动下载 200MB 定制 Chromium

**现象**：第一次调用 `launch()` 时，CloakBrowser 自动从 `cloakbrowser.dev` 下载约 200MB 定制 Chromium 到 `~/.cloakbrowser/`，下载速度可能较慢。

**应对**：Step 5 验证反检测时设置足够长的超时时间（建议 300 秒），等待自动下载完成。如网络极差，可手动下载后放到 `C:\Users\<用户名>\.cloakbrowser\chromium-<版本号>\`（确保 `chrome.exe` 在该目录下）。

### 坑6: jieba 分词库安装失败

**现象**：jieba 包 19.2MB，从 PyPI 下载极慢且 hash 校验失败。

**解决方案**：使用清华镜像源：
```bash
pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple jieba
```

### 坑7: 分析报告生成器 tools/analyzer_redesign.py 不存在

**现象**：项目中默认没有 `tools/analyzer_redesign.py`，boss-analyze skill 引用该文件但需要手动创建。

**解决方案**：在 Step 6 中安装 jieba 后，由 Claude Code 根据项目需要自动生成 `tools/analyzer_redesign.py`，包含：
- jieba 自动关键词提取
- 24 维候选雷达维度池
- P75/P25 动态薪资阈值
- Chart.js 可视化图表
- JS 分页 + 详情弹窗
- 花叔Design 排版样式

## 执行步骤

### Step 0: 环境检测

先创建临时脚本检测环境（避免嵌套引号问题）：

```bash
cat > _env_check.py << 'PYEOF'
from cloakbrowser import launch
browser = launch(headless=True)
page = browser.new_page()
wd = page.evaluate('navigator.webdriver')
ua = page.evaluate('navigator.userAgent')
browser.close()
print(f'STATUS:OK')
print(f'webdriver: {wd}')
print(f'userAgent: {ua}')
PYEOF
cd "D:/AI Projects/offerscope" && source .venv/Scripts/activate 2>/dev/null && python _env_check.py 2>&1
rm -f _env_check.py
```

**判断：**
- 输出包含 `STATUS:OK` 且 `webdriver: False` → 环境已就绪，跳到 Step 6 最终验证
- 报错 `ModuleNotFoundError` → 继续 Step 1
- 其他报错 → 继续 Step 1

### Step 1: 检查前置条件

```bash
python --version && node --version
```

- Python >= 3.9，Node.js >= 18
- 不满足则提示用户先安装

### Step 2: 虚拟环境

`.venv` 目录通常已存在。如不存在：
```bash
cd "D:/AI Projects/offerscope" && python -m venv .venv
```

### Step 3: 安装 Python 依赖

**先升级 pip**，然后用清华镜像安装所有包：

```bash
cd "D:/AI Projects/offerscope" && source .venv/Scripts/activate && python -m pip install --upgrade pip
```

```bash
cd "D:/AI Projects/offerscope" && source .venv/Scripts/activate && pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple "cloakbrowser[geoip]"
```

验证导入：
```bash
cd "D:/AI Projects/offerscope" && source .venv/Scripts/activate && python -c "from cloakbrowser import launch; print('CloakBrowser OK')"
```

### Step 4: 安装 Playwright Chromium（手动方式，避免下载超时）

#### 4a. 清理残留锁文件
```bash
rm -rf "$HOME/AppData/Local/ms-playwright/__dirlock"
```

#### 4b. 获取 Playwright Chromium 下载 URL

运行以下命令，从输出中抄下 zip 下载链接（如 `https://cdn.playwright.dev/builds/cft/xxx/win64/chrome-headless-shell-win64.zip`）：

```bash
cd "D:/AI Projects/offerscope" && source .venv/Scripts/activate && python -c "
from playwright.sync_api import sync_playwright
try:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        print('version:', b.version)
        b.close()
except Exception as e:
    print(e)
" 2>&1
```

报错信息中会包含期望的 zip 路径。**或直接查看 playwright 期望的浏览器版本**：

```bash
cd "D:/AI Projects/offerscope" && source .venv/Scripts/activate && python -c "import playwright; print(playwright.__file__)"
```

#### 4c. 用户手动下载 zip

让用户用浏览器或下载工具下载 zip 文件。下载链接格式：
```
https://cdn.playwright.dev/builds/cft/<chrome版本>/win64/chrome-headless-shell-win64.zip
```

#### 4d. 解压到 Playwright 缓存目录

假设用户下载的 zip 放在 `D:\AI Projects\chrome-headless-shell-win64.zip`：

```bash
# 获取正确的 browser 目录名（由 4b 的报错中可知）
BROWSER_DIR="chromium_headless_shell-1223"  # 根据实际版本调整
mkdir -p "$HOME/AppData/Local/ms-playwright/$BROWSER_DIR"
cd "$HOME/AppData/Local/ms-playwright/$BROWSER_DIR"
unzip -o "D:/AI Projects/chrome-headless-shell-win64.zip"
touch INSTALLATION_COMPLETE
echo "Playwright Chromium installed"
```

### Step 5: 验证反检测

**必须使用临时脚本文件**，不要用 `python -c` 带嵌套引号：

```bash
cat > _verify.py << 'PYEOF'
from cloakbrowser import launch
browser = launch(headless=True)
page = browser.new_page()
wd = page.evaluate('navigator.webdriver')
ua = page.evaluate('navigator.userAgent')
print(f'webdriver: {wd}')
print(f'userAgent: {ua}')
browser.close()
print('验证通过!' if not wd else '验证失败: webdriver未被隐藏')
PYEOF
cd "D:/AI Projects/offerscope" && source .venv/Scripts/activate && python _verify.py 2>&1
rm -f _verify.py
```

首次运行会自动下载约 200MB 的 CloakBrowser 定制 Chromium 到 `~/.cloakbrowser/`，需等待数分钟。

### Step 6: 最终验证报告

```bash
cat > _final_check.py << 'PYEOF'
import cloakbrowser
from pathlib import Path
import subprocess, sys

print("=== BOSS直聘抓取环境验证 ===")
print(f"Python: {sys.version.split()[0]}")

# CloakBrowser
print(f"CloakBrowser: {cloakbrowser.__version__}")

# Playwright
result = subprocess.run([sys.executable, "-m", "pip", "show", "playwright"], capture_output=True, text=True)
for line in result.stdout.splitlines():
    if line.startswith("Version:"):
        print(f"Playwright: {line.split()[1]}")

# CloakBrowser Chromium
cb_dir = Path.home() / ".cloakbrowser"
if cb_dir.exists():
    for d in cb_dir.iterdir():
        if d.is_dir() and d.name.startswith("chromium-"):
            print(f"CloakBrowser Chromium: {d}")

# Playwright Chromium
pw_dir = Path.home() / "AppData" / "Local" / "ms-playwright"
if pw_dir.exists():
    for d in pw_dir.iterdir():
        if d.is_dir() and d.name.startswith("chromium"):
            print(f"Playwright Chromium: {d}")

# Webdriver check
from cloakbrowser import launch
browser = launch(headless=True)
page = browser.new_page()
wd = page.evaluate('navigator.webdriver')
browser.close()
print(f"webdriver: {wd} {'✅' if not wd else '❌ 反检测失败!'}")
print("\n下一步: 使用 boss-scrape 开始抓取")
PYEOF
cd "D:/AI Projects/offerscope" && source .venv/Scripts/activate && python _final_check.py 2>&1
rm -f _final_check.py
```

## 验证方式

1. Step 5 输出 `webdriver: False` 且结尾显示 `验证通过!`
2. Step 3 输出 `CloakBrowser OK`
3. Step 6 汇总所有版本信息，webdriver 必须为 `False`

## 踩坑速查表

| 序号 | 现象 | 原因 | 解决 |
|------|------|------|------|
| 1 | pip install 报 hash mismatch | pip 版本旧 / PyPI 下载慢 | 升级 pip + 用清华镜像 |
| 2 | playwright install 被 kill (137) | CDN 下载太慢 | 手动下载 zip + 解压 |
| 3 | "An active lockfile is found" | 上次被 kill 后残留锁 | `rm -rf __dirlock` |
| 4 | python -c 报 No such file | bash 嵌套引号解析错误 | 用临时 .py 脚本文件 |
| 5 | launch() 卡住很久 | 首次下载 200MB Chromium | 耐心等待 / 手动下载 |
| 6 | jieba hash mismatch | PyPI 下载不稳 | 用清华镜像 |
| 7 | analyzer_redesign.py 不存在 | 项目不含该文件 | 由 Claude Code 自动生成 |
