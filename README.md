# 多 Agent 交叉评审调研平台

面向团队的方案交叉评审工作台。用户可以输入调研主题或上传 PDF、DOCX 方案材料，由文档解析、收益论证、风险研判、事实核查和汇总评审 Agent 协作，输出带来源链接的结构化 Markdown 报告。

## 当前实现

- 后端：FastAPI、SQLAlchemy Async、SSE、JWT、PostgreSQL/Supabase Storage 适配
- 前端：Next.js 16、React 19、TypeScript、Tailwind CSS 4
- 认证：邮箱密码、邮箱验证、密码重置、组织 owner 邀请成员
- 输入：主题或最多 5 个 PDF/DOCX，单文件 20 MB
- 评审：1 至 5 轮，默认 3 轮；收益与风险交替输出，事实核查写入证据池
- 报告：固定五段式 Markdown，支持鉴权下载
- 运行时：阶段一使用自研编排；阶段二可通过 `REVIEW_RUNTIME=langgraph` 接入 LangGraph

## 本地启动

```powershell
cd backend
python -m pip install -r requirements.txt
$env:PYTHONPATH = "."
uvicorn app.main:app --reload --port 8000

cd ..\frontend
npm install
npm run dev
```

开发环境默认使用 SQLite、本地文件存储和控制台邮件。控制台会打印验证和邀请链接。生产环境建议使用 Supabase PostgreSQL/Storage、Resend 和随机 JWT secret。

## Vercel + Render 部署

生产拓扑：Vercel 托管 Next.js 前端，Render 托管 `backend/` Docker 服务，Supabase 提供 PostgreSQL 和私有 Storage，Resend 发送验证/邀请邮件。

### 1. 创建 Supabase 资源

1. 新建 Supabase 项目，在 **Storage** 中创建私有桶 `review-documents`。
2. 在 Project Settings 中复制连接串。后端使用异步驱动格式：
   `postgresql+asyncpg://<user>:<password>@<host>:5432/postgres`。
3. 使用服务端 `service_role` 密钥访问私有桶；该密钥只配置在 Render，不能放进前端或提交到 Git。

### 2. 部署 Render 后端

1. 在 Render 导入此仓库，选择 `refactor-review` 分支；Root Directory 填 `backend`，Runtime 选择 Docker，Dockerfile 使用 `./Dockerfile`。测试阶段可选择 Free 方案（空闲时会休眠，首次请求可能需要等待唤醒）；生产 SSE 建议升级到常驻实例。
2. Render 会注入 `PORT`；`backend/Dockerfile` 已使用该端口启动 Uvicorn。也可以直接使用仓库根目录的 `render.yaml` 创建服务。
3. 配置以下环境变量（值按你的项目替换）：

```text
APP_ENV=production
DEBUG=false
FRONTEND_URL=https://<your-app>.vercel.app
DATABASE_URL=postgresql+asyncpg://<supabase-user>:<password>@<supabase-host>:5432/postgres
JWT_SECRET=<随机的长字符串>
DEEPSEEK_API_KEY=<DeepSeek key>
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
EMAIL_PROVIDER=resend
RESEND_API_KEY=<Resend key>
EMAIL_FROM=Review Platform <noreply@your-domain.example>
STORAGE_PROVIDER=supabase
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service role key>
SUPABASE_STORAGE_BUCKET=review-documents
REVIEW_RUNTIME=custom
MAX_UPLOAD_FILES=5
MAX_UPLOAD_BYTES=20971520
```

4. 部署后在 Render Shell（或一次性任务）执行：

```bash
alembic upgrade head
```

5. 用 `https://<render-domain>/api/health` 检查服务。自定义域名后，将新的前端域名同步更新到 `FRONTEND_URL` 并重新部署。

### 3. 部署 Vercel 前端

1. 在 Vercel 导入同一仓库，Root Directory 选择 `frontend`，Framework 选择 Next.js。
2. 添加环境变量：

```text
NEXT_PUBLIC_API_URL=https://<your-render-service>.onrender.com
```

3. 部署后打开前端注册页，验证注册、邮件验证、登录和新建评审流程。若使用自定义域名，必须同时更新 Render 的 `FRONTEND_URL`。

### 4. SSE、Storage 和安全检查

- Render 反向代理需允许长连接；不要为 `/api/reviews/*/events` 配置短请求超时。
- 浏览器通过带凭据的 `fetch` 读取私有 SSE，前端 API 地址必须使用 HTTPS。
- 登录态使用 HttpOnly Cookie；跨域 Vercel/Render 部署需保持 `credentials` 请求和 HTTPS。
- Supabase 桶保持私有，文件下载只能经过后端鉴权接口。
- 生产日志不要打印 JWT、数据库密码、Resend/DeepSeek/Supabase 密钥；不要提交任何 `.env` 文件。
- `TRUST_PROXY_HEADERS=true` 仅在 Render 等可信反向代理已覆盖转发头时启用；本地保持 `false`。
- 多实例生产环境将 `RATE_LIMIT_BACKEND` 设为 `database`，使用 Supabase PostgreSQL 共享限流；本地可保持 `memory`。

## 数据库迁移

新评审数据库不迁移历史辩论数据。生产部署前执行 `alembic upgrade head`。本地开发仍由应用启动时的 `create_all` 创建表，便于快速验证。

## 验证

```powershell
cd backend
python -m compileall -q app alembic
cd ..\frontend
npm run lint
npm run build
```

部署前还可以在仓库根目录执行：

```powershell
git diff --check
```
