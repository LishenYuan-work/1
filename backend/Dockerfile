# 后端 Dockerfile（Render / 任意 Docker 平台）
FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

# 生产环境必须通过 DATABASE_URL 注入 Supabase PostgreSQL。
ENV DATABASE_URL=sqlite+aiosqlite:///./review_platform.db

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
