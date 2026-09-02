# 多 Agent 交叉评审调研平台开发全过程报告

从原多 Agent 辩论室到团队方案交叉评审工作台的完整历程

版本：v1.0（当前 main）  
生成日期：2026 年 9 月 2 日  
代码基线：`7724030`（`main` / `refactor-review`）

## 目录

1. 项目概述
2. 架构演进总览
3. 第一阶段：原多 Agent 辩论室基线
4. 第二阶段：评审领域重构
5. 第三阶段：认证、组织与部署接入
6. 第四阶段：自研评审编排与证据闭环
7. 第五阶段：前端工作台完整重设计
8. 错误与修复汇总
9. 数据库设计
10. 文件变更清单与关键代码
11. 当前架构、验证结果与能力边界
12. 经验教训与后续优化方向

## 一、项目概述

### 1.1 项目简介

多 Agent 交叉评审调研平台面向团队内部的方案评审和调研工作。用户可以输入调研主题，或上传 PDF、DOCX 方案材料；平台由文档解析、收益论证、风险研判、事实核查和汇总评审五个固定 Agent 协作，形成可追溯的 Markdown 评审报告。

平台的定位是“辅助研究与结构化审阅”，不是自动决策系统。事实核查没有获得可靠链接时必须标记为“待确认”，不会凭空补充来源。

### 1.2 技术栈

| 层级 | 当前方案 |
|---|---|
| 前端 | Next.js 16、React 19、TypeScript、Tailwind CSS 4 |
| 后端 | Python、FastAPI、SQLAlchemy Async |
| 数据库 | PostgreSQL（Supabase），本地开发可用 SQLite |
| 认证 | Supabase Auth 邮箱密码、邮箱验证、密码重置；后端换发 HttpOnly JWT Cookie |
| 文件存储 | Supabase Storage 私有桶；本地开发支持本地目录 |
| 实时通信 | 带鉴权请求头的 SSE `fetch` 流式解析 |
| 模型 | OpenAI 兼容的 DeepSeek 客户端，可配置模型和地址 |
| 搜索 | DuckDuckGo Search（`ddgs`）联网检索适配 |
| 文档解析 | PyPDF2、python-docx；解析放入线程执行 |
| 部署 | Vercel 前端、Render 后端、Supabase 数据与存储 |
| 第二阶段运行时 | 已提供 LangChain / LangGraph 适配代码，默认仍为自研编排 |

### 1.3 核心功能

- 主题输入或 PDF/DOCX 材料上传
- 单任务最多 5 个文件、单文件不超过 20 MB
- 1 至 5 轮评审，默认 3 轮
- 每轮固定执行“收益论证 → 事实核查 → 风险研判 → 事实核查”
- 五个 Agent 的实时活动展示和断线恢复
- 证据池保存论据、核查结论、理由和来源链接
- 固定五段式 Markdown 报告和下载接口
- 邮箱验证、忘记密码、重置密码
- 组织 owner 邀请成员，评审任务按组织隔离
- 1440×900 桌面基准和移动端抽屉式导航

## 二、架构演进总览

项目先验证了原有多 Agent 对话/辩论产品的可运行性，随后根据团队评审场景完成领域重构。主要变化如下：

| 阶段 | 时间 | 主要形态 | 状态 | 变化原因 |
|---|---|---|---|---|
| 基线 | 2026-07-29 至 07-30 | 多 Agent 辩论室、事实核查页 | 已运行 | 验证 SSE、鉴权和模型调用基础设施 |
| 领域重构 | 2026-08-26 | 评审会话、证据池、固定 Agent | 已完成 | 删除辩论领域，聚焦方案交叉评审 |
| 平台接入 | 2026-08-27 至 08-28 | Supabase Auth、Render、Vercel | 已完成 | 支持团队账户、云数据库和私有存储 |
| 体验完善 | 2026-08-30 至 08-31 | 工作台、编排、证据库、系统设置 | 已完成 | 完成公开预览和 B 端工具化 UI |
| 运行时准备 | 当前 | 可切换 LangGraph 运行时 | 代码已提供，默认关闭 | 保持业务 API 与 SSE 契约稳定，分阶段迁移 |

关键提交节点：

- `f5a9fb8`：替换辩论室为评审平台
- `07b102a`：接入 Supabase Auth 会话交换
- `cd9f093`：加固 SSE 鉴权和事件类型
- `fce83a1`：允许未登录用户浏览工作台预览
- `a37fedc`：增加预计耗时、编排和设置能力
- `07b362d`、`e72b2fc`：修复生产 API 地址和 Vercel CORS
- `f65d577`：修复报告完成后 Agent 状态滞留
- `7724030`：加固认证 Cookie 和生产邮件适配

## 三、第一阶段：原多 Agent 辩论室基线

### 3.1 初始设计

原项目包含辩论会话、角色配置、辩论模板、评论和事实核查页面。早期实现重点验证：

- FastAPI 接口和异步数据库会话
- JWT 登录态和游客/手机号登录路径
- SSE 或轮询方式的实时输出
- PDF、Word 和文本材料解析
- 联网搜索注入模型提示词
- Next.js 多页面交互

### 3.2 基线暴露的问题

- 领域模型围绕辩手、立场、追问和评论展开，与方案评审目标不一致
- 前端页面存在辩论席位、发言时间线等不适用的产品概念
- 旧数据库字段和接口会让评审数据边界不清晰
- 早期多种登录方案并存，生产部署时容易误用本地 API 地址
- SSE 事件依赖内存状态时，刷新页面后无法可靠恢复 Agent 状态

这些问题促成了后续“新评审数据库 + 新路由 + 新工作台”的整体重构，而不是在旧辩论模型上继续叠加功能。

## 四、第二阶段：评审领域重构

### 4.1 删除范围

删除了旧辩论路由、服务、角色、Prompt、评论组件、辩论页面、旧 CLI 和重复的根目录编排实现。历史提交仍保留在 Git 历史中，但当前运行代码不再提供辩论业务接口。

### 4.2 新的五 Agent 职责

| Agent | 输入 | 输出 |
|---|---|---|
| 文档解析 | 主题、PDF/DOCX 提取文本、初步检索资料 | 核心观点、指标、约束和摘要 |
| 收益论证 | 文档摘要、主题、轮次 | 收益和有利条件论据 |
| 风险研判 | 文档摘要、主题、收益输出、轮次 | 风险、缺陷和落地约束论据 |
| 事实核查 | 每条论据 | `verified`、`contradicted` 或 `uncertain`，绑定来源 |
| 汇总评审 | 已持久化输出和证据池 | 固定五段式 Markdown 报告 |

### 4.3 评审顺序

```text
主题/文档 → 文档解析 →
  第 1 轮：收益论证 → 核查 → 风险研判 → 核查 →
  第 2 轮：收益论证 → 核查 → 风险研判 → 核查 → … →
汇总评审 → 报告
```

每个节点输出都经过结构化 JSON 校验；校验失败会自动重试一次，仍失败则记录 Trace 和阶段错误。

## 五、第三阶段：认证、组织与部署接入

### 5.1 认证流程

当前生产路径由 Supabase Auth 管理邮箱注册、邮箱验证和密码重置。前端获得 Supabase Session 后调用 `/api/auth/supabase/exchange`，后端校验远端用户并换发自己的 HttpOnly JWT Cookie。评审 API 仍由后端统一鉴权，避免将服务密钥暴露给浏览器。

### 5.2 组织权限

- 首个注册用户创建组织并成为 owner
- owner 可发送邀请、查看成员和移除普通成员
- 评审查询必须带组织成员关系
- 跨组织资源统一返回 404
- 评审创建者或组织 owner 可删除评审
- 只有创建者或 owner 可处理 LangGraph 人工复核节点

### 5.3 部署拓扑

```text
浏览器 → Vercel Next.js 前端
             │ HTTPS + credentials + CORS
             ▼
       Render FastAPI 后端
          ├─ Supabase PostgreSQL
          ├─ Supabase Auth
          ├─ Supabase 私有 Storage
          ├─ DeepSeek OpenAI 兼容接口
          └─ DuckDuckGo Search
```

生产密钥通过 Render/Vercel 环境变量注入；`SUPABASE_SERVICE_ROLE_KEY` 只允许出现在后端环境，不进入前端构建。

## 六、第四阶段：自研评审编排与证据闭环

### 6.1 文档处理

上传接口先限制文件名、格式、大小和 PDF/DOCX 文件签名，再在线程中执行文本提取。扫描件没有 OCR 能力时返回明确错误。无文档时，文档解析 Agent 基于主题调用搜索，并使用相关性过滤避免把无关结果送入模型。

### 6.2 证据持久化

事实核查对每条论据单独检索：

1. 写入“正在核查”事件
2. 调用现有搜索工具
3. 过滤无效 URL
4. 生成核查结论和理由
5. 写入 `evidence_pool` 与 `evidence_sources`
6. 先提交数据库，再广播 SSE 事件

没有可靠来源的论据进入 `uncertain`，报告中进入“待确认不确定性点”。

### 6.3 SSE 事件契约

固定事件类型为：`session_status`、`document_status`、`agent_start`、`agent_chunk`、`agent_result`、`evidence_upsert`、`round_complete`、`report_ready`、`error`、`done`。

每条事件写入 `review_events`，带单调递增 `sequence`。前端通过 `Last-Event-ID` 请求未接收事件，服务重启后的未完成任务标记为 `interrupted`，允许重新执行。

### 6.4 报告结构

报告必须严格按以下顺序生成：

```markdown
## 方案概述
## 收益清单
## 风险与隐患清单
## 待确认不确定性点
## 参考证据来源列表
```

汇总 Agent 只读取已持久化的 Agent 输出和证据，不直接相信未落库的临时文本。

## 七、第五阶段：前端工作台完整重设计

### 7.1 页面结构

- 左侧：组织工作区、评审历史、新建评审入口
- 顶部：面包屑、连接状态、帮助和登录/新建按钮
- 输入区：主题、多轮次选择、PDF/DOCX 队列和启动按钮
- 活动区：五个 Agent 卡片、流式文本和完成状态
- 证据区：论据核查状态、来源展开、外部链接
- 报告区：Markdown 预览、下载和删除操作
- 二级页面：Agent 编排、证据库、系统设置

### 7.2 视觉与交互

前端采用冷白/浅绿色背景、细边框、毛玻璃面板、6 至 10px 圆角和单一绿色强调色。页面支持未登录预览，但上传、启动、查看组织数据和下载报告都要求登录。

已处理的交互状态包括：空状态、上传格式错误、20 MB 限制、按钮禁用、加载骨架、SSE 重连、模型失败、解析失败、人工复核和移动端抽屉导航。

### 7.3 示例材料

当前内置三个快速开始主题，用于演示而不是限制审查范围：

- 企业知识库升级
- 客服自动化项目
- 数据平台整合

实际可审查对象包括技术方案、立项材料、产品规划、采购方案、数据治理、AI 应用、市场调研、合规安全和实施计划等，只要用户提供主题或 PDF/DOCX 材料即可。

## 八、错误与修复汇总

| 问题 | 根因 | 修复 |
|---|---|---|
| 主题检索返回无关内容导致解析失败 | 搜索服务偶发返回不相关结果 | 增加主题相关性过滤和空结果兜底 |
| 模型返回非标准 JSON | 模型输出存在 Markdown 或字段别名 | 增加一次重试、结果归一化和严格校验 |
| 汇总模型失败导致整场评审失败 | 报告阶段缺少可靠兜底 | 使用持久化输出和证据生成报告兜底 |
| 生产登录显示 `Failed to fetch` | Vercel 构建缺少 API 地址时请求本机 localhost | 增加 Render API 生产 fallback 和中文连接错误 |
| Vercel 请求被 CORS 拒绝 | 预览域名包含分支别名和部署别名 | 增加受限的 Vercel 域名匹配，同时保留 FRONTEND_URL 白名单 |
| 报告完成后两个 Agent 仍显示处理中 | 事实核查和汇总没有完整完成事件/持久化输出 | 补充 `agent_result`，前端终态以持久化状态为准 |
| Supabase 用户误走本地密码登录可能 500 | Supabase profile 的 `password_hash` 为空 | 登录前显式检查空密码哈希并返回统一凭据错误 |
| 记住我有效期与 Cookie 不一致 | JWT 和 Cookie 使用了不同生命周期 | 按 `remember_me` 同步 Cookie 的 `Max-Age` |
| 组织邀请邮件静默丢失 | `EMAIL_PROVIDER=supabase` 没有后端邮件实现 | Render 改用 Resend，未知 provider 显式报错 |

## 九、数据库设计

### 9.1 当前表

| 表 | 用途 |
|---|---|
| `profiles` | 平台用户和验证状态 |
| `organizations` | 组织工作区 |
| `organization_members` | 用户与组织的角色关系 |
| `organization_invites` | 72 小时有效的一次性邀请哈希 |
| `email_tokens` | 24 小时验证令牌和密码重置令牌哈希 |
| `review_sessions` | 评审主题、轮次、阶段、状态和序列计数器 |
| `review_documents` | 原文件元数据、摘要文本和存储路径 |
| `review_outputs` | 每个 Agent 的结构化输出 |
| `review_events` | 可回放 SSE 事件 |
| `evidence_pool` | 论据、核查结论和理由 |
| `evidence_sources` | 证据来源标题、URL、摘要和检索时间 |
| `review_reports` | 最终 Markdown 报告 |
| `review_traces` | 节点耗时、Token 估算、模型和错误 |
| `rate_limit_buckets` | PostgreSQL 共享限流计数 |

### 9.2 迁移策略

新数据库使用 Alembic 初始迁移，不迁移旧辩论数据。当前迁移链为：

```text
0001_review_platform
  → 0002_review_sequences_tokens
  → 0003_rate_limit_bucket
  → 0004_supabase_auth
```

本地开发可以由 `create_all` 创建表；生产由容器启动命令执行 `alembic upgrade head`。

## 十、文件变更清单与关键代码

### 10.1 删除/替换的领域文件

- `backend/app/routers/debates.py`
- `backend/app/routers/templates.py`
- `backend/app/routers/comments.py`
- `backend/app/routers/fact_check.py`
- `backend/app/services/debate_service.py`
- `backend/app/services/fact_check_service.py`
- `backend/src/` 下旧角色、Prompt、编排器和 LLM 实现
- `frontend/src/app/create/`、`dashboard/`、`debate/[id]/`、`fact-check/`
- 根目录旧 CLI、WebUI、启动脚本和旧历史 JSON

### 10.2 新增/重写的核心文件

- `backend/app/routers/reviews.py`
- `backend/app/services/review_service.py`
- `backend/app/services/document_service.py`
- `backend/app/services/storage_service.py`
- `backend/app/services/email_service.py`
- `backend/app/runtime/langgraph_runtime.py`
- `backend/app/runtime/langgraph_nodes.py`
- `backend/alembic/versions/0001_review_platform.py` 至 `0004_supabase_auth.py`
- `frontend/src/app/page.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/auth.tsx`
- `frontend/src/lib/use-sse.ts`
- `frontend/src/lib/supabase.ts`

### 10.3 关键代码片段

生产 API 地址具备本地/线上区分：

```ts
const configuredBase = process.env.NEXT_PUBLIC_API_URL?.trim();
const BASE = (configuredBase || (
  process.env.NODE_ENV === "production"
    ? "https://review-platform-api.onrender.com"
    : "http://localhost:8000"
)).replace(/\/$/, "");
```

评审报告完成后写入 Agent 输出和报告：

```python
markdown = _normalize_report(summary["markdown"], session, evidence)
await save_output(db, session, "summary_report", session.max_round, markdown, summary)
db.add(ReviewReport(session_id=session.id, markdown=markdown))
session.status = "completed"
session.current_stage = "completed"
```

## 十一、当前架构、验证结果与能力边界

### 11.1 当前运行方式

默认配置 `REVIEW_RUNTIME=custom`，由 `review_service.py` 负责顺序调度、数据库写入和 SSE 广播。LangGraph 代码已实现可切换入口，但需要生产 PostgreSQL checkpoint 和完整环境配置后再启用。

### 11.2 自动化验证

- 后端契约测试：`11 passed`
- 前端 ESLint：通过
- Next.js 16 生产构建：通过
- Alembic 四个迁移：临时 SQLite 验证通过
- Git 分支：`main` 与 `refactor-review` 同步到 `7724030`
- 生产健康检查：Render `/api/health` 返回正常
- 生产 CORS：当前 Vercel 预览来源预检返回 `200`

### 11.3 真实服务验收边界

以下项目不能仅靠本地自动化证明，需要部署账户中的真实配置：

- Supabase Auth 的真实注册、验证和重置邮件
- Resend 组织邀请邮件送达
- DeepSeek 真实模型响应和 Token 统计
- DuckDuckGo 真实网络搜索稳定性
- Supabase Storage 私有桶上传/删除策略
- Render 长连接、休眠唤醒和多实例限流表现

### 11.4 明确限制

- 不支持扫描版 PDF OCR
- 搜索结果质量受外部搜索服务影响
- AI 输出属于辅助评审，不替代法律、医疗、投资等专业判断
- 当前自研编排服务重启后只能将任务标记为中断并重跑，真正的断点续跑留给 LangGraph checkpoint 阶段

## 十二、经验教训与后续优化方向

### 12.1 经验教训

1. 领域重构应先冻结接口和数据边界，再删除旧业务，避免辩论概念继续渗透到新页面。
2. 所有模型输出都要经过结构化校验和可解释兜底，不能把模型文本直接当作业务状态。
3. SSE 必须“先落库、后广播”，前端状态必须能从持久化详情重新计算。
4. 分离部署时，API 地址、CORS、Cookie、CSRF 和 Supabase Redirect URL 必须作为一条链路联调。
5. 服务商适配器必须对未知配置显式失败，不能把“打印日志”误认为“邮件已发送”。
6. 产品预览可以公开，但任何组织数据、上传和执行操作都必须经过认证。

### 12.2 后续优化优先级

| 优先级 | 优化项 | 说明 |
|---|---|---|
| P0 | 真实服务验收 | 用真实 Supabase、Resend、DeepSeek 和 Storage 跑完整主题/多文档评审 |
| P0 | LangGraph PostgreSQL checkpoint | 启用暂停、恢复、人工复核和服务重启续跑 |
| P1 | 增加 Playwright E2E | 覆盖登录、上传、SSE 合并、证据展开、报告下载和移动端布局 |
| P1 | 事件/状态对照测试 | 保证断线恢复不重复写证据、不重复创建报告 |
| P1 | 搜索来源质量评分 | 增加来源域名、发布时间和可引用性排序 |
| P2 | 文档分块与摘要缓存 | 降低多文档长上下文的模型成本和延迟 |
| P2 | 成员管理页面 | 展示成员列表、邀请状态和移除操作 |
| P2 | 报告版本和批注 | 支持团队复核、标注和版本对比 |
| P3 | OCR 和更多格式 | 在明确成本与隐私策略后增加扫描 PDF、PPTX 等格式 |

— 文档结束 —
