# 🎤 多Agent辩论室

> 多个 AI Agent 扮演不同角色，围绕任意话题展开多轮深度辩论。支持实时流式观看、追问辩手、评论互动。

**在线体验：** [https://1-peach-theta.vercel.app](https://1-peach-theta.vercel.app)

## ✨ 特性

- 🎭 **多角色辩论** — 2~8 个 AI Agent，各自拥有独立立场和人格
- 📋 **4 套预设模板** — 正反辩论 / 多视角分析 / 决策论证 / 学术讨论
- 🤖 **AI 角色推荐** — 输入话题，AI 自动推荐最适合的辩论阵容
- ⚡ **实时流式** — SSE 逐字推送，看到 AI 实时打字发言
- 💬 **追问 & 评论** — 辩论结束后追问任意辩手，围观用户可评论互动
- 🔐 **用户系统** — JWT 注册/登录，个人辩论历史
- 🌐 **公网部署** — 一键部署到 Vercel + Render + Supabase，完全免费

## 🏗️ 架构

```
用户浏览器 (Next.js)
       │
       ├── REST API (JSON) ──→ FastAPI 后端
       ├── SSE 流式 ──────────→ FastAPI 辩论引擎
       │                            │
       │                    ┌───────┴───────┐
       │                    │  DeepSeek API │
       │                    └───────────────┘
       │
       └── 数据持久化 ──→ PostgreSQL (Supabase / Render)
```

| 层 | 技术 | 部署 |
|---|------|------|
| 前端 | Next.js 16 + TypeScript + Tailwind CSS | Vercel |
| 后端 | FastAPI + SQLAlchemy async | Render |
| 数据库 | PostgreSQL | Supabase / Render |
| AI | DeepSeek API (OpenAI 兼容) | - |
| 实时 | Server-Sent Events | - |

## 🚀 本地运行

### 环境要求

- Python 3.12+
- Node.js 20+
- DeepSeek API Key（[获取地址](https://platform.deepseek.com/api_keys)）

### 1. 克隆仓库

```bash
git clone https://github.com/lishenyuan001/-1.git
cd -1
```

### 2. 启动后端

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

### 3. 启动前端

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

### 4. 打开浏览器

访问 http://localhost:3000

## 🔧 .env 配置说明

后端 `backend/.env`：

```bash
DEEPSEEK_API_KEY=sk-your-key-here    # 必填
DATABASE_URL=sqlite+aiosqlite:///./debate.db  # 本地 SQLite，生产用 PostgreSQL
JWT_SECRET=your-random-secret        # 生产环境务必更换
DEBUG=true
```

前端 `frontend/.env.local`：

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 📁 项目结构

```
├── frontend/                  # Next.js 前端
│   ├── src/
│   │   ├── app/               # 页面路由
│   │   ├── components/        # React 组件
│   │   └── lib/               # API 客户端、Auth、SSE Hook
├── backend/                   # FastAPI 后端
│   ├── app/
│   │   ├── routers/           # API 路由 (auth/debates/comments/templates)
│   │   ├── services/          # 业务逻辑（辩论编排）
│   │   ├── core/              # 配置、安全、限流、SSE 管理
│   │   └── db/                # 数据库模型
│   └── src/                   # 原有辩论引擎
│       ├── orchestrator.py    # 核心调度器
│       ├── roles.py           # 角色系统
│       └── prompts.py         # Prompt 模板
└── supabase/
    └── migrations/            # 数据库迁移 SQL
```

## 🌍 一键部署（免费）

| 步骤 | 平台 | 说明 |
|------|------|------|
| 1 | [Render](https://render.com) | 创建 PostgreSQL + Web Service，部署 `backend/` |
| 2 | [Vercel](https://vercel.com) | 部署 `frontend/`，设置 `NEXT_PUBLIC_API_URL` |
| 3 | 设置环境变量 | `DATABASE_URL`、`DEEPSEEK_API_KEY`、`JWT_SECRET` |

## 📄 License

MIT
