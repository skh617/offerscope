# BOSS 直聘岗位追踪系统 — 需求文档 v2

> 2026-06-04 讨论沉淀。v2 的核心变化：从 CLI 工具升级为 Web 服务，支持分享链接给他人使用。

## 1. 产品概述

### 1.1 项目定位

v1 实现了 CLI 工具形态的完整管道（抓取 → 趋势 → 分析 → 飞书推送），但仅限本地使用。v2 的目标是 **Web 化**：将系统包装为一个 Web 服务，分享链接给他人即可使用，无需对方安装任何环境。

### 1.2 v2 核心用户场景

1. 用户 A 把服务部署在自己的电脑上，通过内网穿透获得公开 URL
2. 用户 B 打开这个 URL，看到表单页 + 最近报告列表
3. 用户 B 填写：岗位名（必填）、城市（选填默认北京）、抓取数量（选填默认10上限50）、飞书 Webhook（选填）
4. 点击"开始分析"，页面上实时显示抓取进度
5. 填了 Webhook → 后台推送到飞书，页面显示"已推送"
6. 没填 Webhook → 页面直接展示完整分析报告
7. 所有报告持久保存，可在"最近报告"列表中随时回顾

### 1.3 与 v1 的关系

v1 的 CLI 管道（`scheduler.py` + `config.yaml` + `tools/`）**保持不变，继续可用**。v2 的 Web 层是对 v1 能力的封装和暴露，核心分析逻辑完全复用。

### 1.4 当前阶段边界

| 维度 | v1 范围 | v2 变化 |
|------|---------|---------|
| 平台 | BOSS 直聘 | 不变 |
| 抓取方式 | CLI 手动触发 + config.yaml 驱动 | 新增 Web 表单触发，CLI 保持可用 |
| 推送渠道 | 飞书 Webhook | 不变；新增 Web 页面直接查看（无需 webhook） |
| 部署形态 | 本地运行 | 本地运行 + Cloudflare Tunnel 内网穿透 |
| 用户界面 | 终端 + 飞书卡片 | 新增 Web 前端（表单 + 进度 + 报告展示） |

---

## 2. 功能需求

### 2.1 Web 前端

#### 2.1.1 页面结构

单页应用（SPA），包含以下区域：

| 区域 | 内容 |
|------|------|
| 顶部 | 项目标题 + 一句话简介 |
| 表单区 | 岗位名 input（必填）+ 城市 select + 数量 input + 飞书 webhook input + 提交按钮 |
| 进度区 | 提交后动态展示：当前阶段、进度文字、已完成阶段的勾选 |
| 结果区 | 已完成时展示：飞书推送成功提示 + "查看报告"按钮；或直接 iframe 内嵌报告 |
| 底部 | 最近报告列表（卡片式，按时间倒序） |

#### 2.1.2 表单字段

| 字段 | 类型 | 必填 | 默认值 | 约束 |
|------|------|------|--------|------|
| 岗位名称 | 文本输入 | 是 | — | 任意中文/英文 |
| 城市 | 下拉选择 | 否 | 北京 | 北京/上海/广州/深圳/杭州/成都/南京/武汉/西安 |
| 抓取数量 | 数字输入 | 否 | 10 | 上限 50（防滥用） |
| 飞书 Webhook | 文本输入 | 否 | — | 格式校验 `https://open.feishu.cn/` 前缀 |

#### 2.1.3 进度展示

抓取过程分为 5 个阶段，前端每 3 秒轮询一次状态：

| 阶段 | 进度文字示例 |
|------|-------------|
| 1. 启动 | "正在启动浏览器..." |
| 2. 搜索 | "正在搜索岗位: AI应用后端工程师..." |
| 3. 采集详情 | "正在获取岗位详情 (3/10)..." |
| 4. 生成报告 | "正在生成分析报告..." |
| 5. 完成 | "报告已生成" / "已推送到飞书" |

异常时显示错误信息，并提供"重新抓取"按钮。

#### 2.1.4 结果展示

- **填了 webhook**：显示"已推送飞书 ✅"，下方提供"查看完整报告"按钮，点击后弹窗或跳转
- **没填 webhook**：页面内嵌 iframe 展示完整 HTML 报告，或直接渲染报告内容

#### 2.1.5 最近报告列表

- 扫描 `reports/` 目录，按文件修改时间倒序
- 每项显示：关键词、城市、生成时间、岗位数量
- 点击进入对应报告详情页
- 支持分页（每页 10 条）

### 2.2 Web 后端

#### 2.2.1 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| Web 框架 | FastAPI | 异步友好、自动生成 API 文档、部署简单 |
| 任务执行 | `threading.Thread` | 抓取是同步阻塞操作（Playwright），放在独立线程不阻塞事件循环 |
| 状态管理 | 内存 `dict` | 单机低频使用，无需引入数据库 |
| 前端 | 内嵌 HTML（Python 字符串） | 零前端依赖，一个 `web_app.py` 即可运行 |

#### 2.2.2 API 路由

| 方法 | 路径 | 功能 | 请求体 / 参数 |
|------|------|------|-------------|
| `GET` | `/` | 返回前端页面（HTML） | — |
| `POST` | `/api/scrape` | 创建抓取任务 | `{keyword, city?, max_jobs?, webhook?}` |
| `GET` | `/api/status/{job_id}` | 查询任务状态 | — |
| `GET` | `/report/{job_id}` | 查看报告 | — |
| `GET` | `/api/reports` | 报告列表（最近10条） | — |

#### 2.2.3 POST /api/scrape 处理流程

```
1. 参数校验（keyword 非空、max_jobs ≤ 50）
2. 生成 job_id（uuid 前 8 位）
3. 创建 JobState（status=pending, progress="排队中..."）
4. 启动后台线程执行：
   a. 调用 tools.scraper.scrape(keyword, city, code, max_jobs, headless=False, on_progress=callback)
      - on_progress 回调实时更新 JobState.progress
   b. 调用 tools.analyzer.analyze(jobs) 生成 HTML
   c. 保存报告到 reports/web_{job_id}.html
   d. 如果 webhook 非空：调用 tools.publisher.push(...)
   e. 更新 JobState.status = "done"
5. 立即返回 {job_id, status: "pending"}
```

#### 2.2.4 任务状态模型

```
status: "pending" → "running" → "done"
                              → "error"
```

| 字段 | 说明 |
|------|------|
| `job_id` | 任务唯一标识（8 位 hex） |
| `status` | pending / running / done / error |
| `progress` | 当前阶段文字描述 |
| `keyword` | 岗位关键词 |
| `city` | 城市 |
| `jobs_count` | 抓取到的岗位数（完成后填充） |
| `report_url` | 报告相对路径（完成后填充） |
| `webhook_sent` | 是否已推送飞书 |
| `error` | 错误信息（失败时填充） |
| `created_at` | 任务创建时间 |

### 2.3 抓取适配

#### 2.3.1 scraper.py 改动

`scrape()` 函数新增两个可选参数，**向后兼容，不影响现有 CLI 调用**：

```python
def scrape(keyword, city_name, city_code, max_jobs=40, pages_per_search=2,
           headless=False,     # 新增：Web 调用时默认有头模式
           on_progress=None):  # 新增：进度回调 fn(msg: str)
```

内部：关键 print 语句同时调用 `on_progress(msg)`（若传入），使 Web 后端能实时获取进度。

#### 2.3.2 登录策略

v2 沿用 v1.2.1 的策略，暂时不做远程扫码：

- 部署者在自己电脑启动服务前，先手动运行一次确保登录态有效
- 服务运行期间，CloakBrowser 持久化 session 自动复用
- 会话过期时，任务失败并提示，部署者手动重新登录后恢复

> 远程扫码登录（v1.2）延后实现。Web 化先跑通核心流程。

### 2.4 部署方案

#### 2.4.1 当前阶段：本地 + 内网穿透

```
本地电脑（Windows/macOS）
├── python web_app.py          ← Web 服务，端口 8090
├── CloakBrowser (有头模式)     ← 爬虫需要图形界面
└── cloudflared tunnel         ← 内网穿透，暴露 https://xxx.trycloudflare.com
```

**为什么不是 Docker / 云服务器：**
- CloakBrowser 需要图形界面（有头模式反检测效果最好）
- 本地部署零成本，国内访问快
- 先跑通再考虑迁移

**后续可选升级路径：**
- 云服务器 + xvfb 虚拟显示 → Render/Railway 免费层
- 阿里云 ECS → 国内体验最好的付费方案

#### 2.4.2 启动步骤

```bash
# 终端 1：启动 Web 服务
python web_app.py

# 终端 2：启动内网穿透（需要先安装 cloudflared）
cloudflared tunnel --url http://localhost:8090
# 输出：https://xxx.trycloudflare.com → 分享这个链接
```

---

## 3. 系统架构

### 3.1 v2 文件结构

```
offerscope/
├── config.yaml                  # v1：CLI 任务配置（保持不变）
├── scheduler.py                 # v1：CLI 调度入口（保持不变）
├── web_app.py                   # 新增：Web 服务入口（FastAPI）
├── templates/
│   └── index.html               # 新增：前端单页（可选，也可内嵌在 web_app.py 中）
├── tools/
│   ├── scraper.py               # 小改：scrape() 增加 headless/on_progress 参数
│   ├── analyzer.py              # 不改
│   ├── trend.py                 # 不改
│   └── publisher.py             # 不改
├── serve.py                     # v1：本地报告 HTTP 服务（v2 可废弃，web_app.py 替代）
├── data/                        # JSON 岗位数据（v1 + v2 共享）
│   ├── *_jobs.json
│   └── *_jobs.csv
└── reports/                     # HTML 分析报告（v1 + v2 共享）
    ├── *_分析报告.html           # v1 CLI 生成的报告
    └── web_{job_id}.html        # v2 Web 生成的报告
```

### 3.2 v2 执行流程

```
用户浏览器
    │
    │  POST /api/scrape {keyword, city, max_jobs, webhook}
    ▼
web_app.py
    │
    │  创建 JobState → 启动后台线程
    ├──────────────────────────────────────────┐
    │  轮询 GET /api/status/{job_id}           │  后台线程：
    │  (每 3 秒，展示进度)                      │
    │                                          ├── scraper.scrape()
    │                                          │     → data/*_jobs.json
    │   状态 done → 展示报告                    │
    │                                          ├── analyzer.analyze()
    │                                          │     → reports/web_{job_id}.html
    │                                          │
    │                                          └── 如果 webhook 非空:
    │                                                publisher.push()
    │                                                  → 飞书卡片
    ▼
用户看到报告（iframe 或跳转 /report/{job_id}）
```

### 3.3 与 v1 的共存关系

```
          ┌──────────────┐     ┌──────────────┐
          │  v1: CLI     │     │  v2: Web     │
          │  scheduler   │     │  web_app     │
          └──────┬───────┘     └──────┬───────┘
                 │                    │
                 └────────┬───────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
          scraper     analyzer    publisher
              │           │           │
              ▼           ▼           ▼
          data/       reports/    飞书 Webhook
```

v1 和 v2 共享同一套核心模块和数据目录，互不干扰。

---

## 4. 非功能需求

### 4.1 模块独立性

- v2 新增文件 `web_app.py` 对 v1 核心模块零侵入（仅 `scraper.py` 的 `scrape()` 增加两个可选参数）
- v1 CLI 所有功能保持可用，不受 v2 影响
- 报告和数据文件 v1/v2 共享同一目录，命名规则区分（v1: 日期前缀，v2: `web_{job_id}.html`）

### 4.2 并发限制

- 同时只允许一个抓取任务运行（单 Chromium 实例限制）
- 新请求在已有任务运行中时返回 `{error: "已有任务正在执行，请稍后再试"}`
- 不需要任务队列（低频使用场景，队列无意义）

### 4.3 安全

- `max_jobs` 硬上限 50，防止恶意大量抓取
- Webhook URL 做前缀校验 `https://open.feishu.cn/`
- 不存储任何用户信息，无认证需求（内网穿透 URL 本身就是访问控制）

### 4.4 容错

- 抓取失败：错误信息展示在前端，提供重试按钮
- 飞书推送失败：不影响报告生成，前端提示"推送失败，可直接查看报告"
- 浏览器崩溃：后台线程捕获异常，标记任务为 error

---

## 5. 后续版本规划

| 版本 | 功能 | 状态 |
|------|------|------|
| v1.0 | CLI 管道（抓取→趋势→分析→推送） | ✅ 已完成 |
| v2.0 | Web 化（表单→进度→报告→最近列表） | 📋 当前计划 |
| v2.1 | 定时调度（APScheduler / cron） | 延后 |
| v2.2 | 远程扫码登录（截图 → 飞书推送 → 手机扫码） | 延后 |
| v2.3 | 多平台扩展（拉勾、猎聘） | 延后 |
| v2.4 | 多渠道推送（钉钉、企业微信） | 延后 |
| v2.5 | SQLite 数据库迁移 | 延后 |
| v2.6 | AI 技能匹配 & 简历差距分析 | 延后 |

> v1.4 原计划的 "Web 管理面板" 被 v2.0 替代和升级。

---

## 6. 术语表

| 术语 | 说明 |
|------|------|
| 采样快照 | 一次抓取获得的所有岗位数据，视为该时刻的市场横截面 |
| 环比 | 本次快照与上一次快照之间的数值变化 |
| 高薪分水岭技能 | 高薪岗位（P75+）中高频出现、入门岗位（P25-）中少见的技能词 |
| 技能提及率 | 某一技能词在 JD 描述中出现的岗位数 / 总岗位数 |
| 主流经验/学历 | 所有岗位中占比最高的经验/学历区间 |
| 内网穿透 | 通过 Cloudflare Tunnel 等技术将本地端口暴露到公网 HTTPS URL |

---

## 附录 A：与 v1 的差异摘要

| 维度 | v1 | v2 |
|------|----|----|
| 触发方式 | CLI `python scheduler.py` | Web 表单提交 |
| 配置方式 | 编辑 `config.yaml` | 表单实时填写 |
| 进度反馈 | 终端 print | 前端轮询进度条 |
| 报告查看 | `python serve.py` + 浏览器打开 | 页面内嵌查看，无需额外步骤 |
| 飞书推送 | 编辑 config.yaml 固定 webhook | 表单选填，灵活切换 |
| 用户门槛 | 需要 Python 环境 + 依赖安装 | 打开链接即可使用 |
| 多人共享 | 不支持 | 一个链接多人使用 |
