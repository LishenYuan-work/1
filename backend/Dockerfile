# 后端 Dockerfile（Railway / 任意云平台部署）
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

# 数据库（SQLite 生产不可用，这里仅用于快速测试；
# 生产环境设置 DATABASE_URL 指向 Supabase/PostgreSQL）
ENV DATABASE_URL=sqlite+aiosqlite:///./debate.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
