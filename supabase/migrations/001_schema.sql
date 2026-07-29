-- Supabase 数据库迁移（生产环境）
-- 本地开发用 SQLite，此文件供 Supabase 部署时使用

-- 辩论表
CREATE TABLE IF NOT EXISTS debates (
    id          TEXT PRIMARY KEY,
    topic       TEXT NOT NULL,
    rounds      SMALLINT NOT NULL DEFAULT 3,
    status      TEXT NOT NULL DEFAULT 'pending',
    visibility  TEXT NOT NULL DEFAULT 'public',
    mode        TEXT NOT NULL DEFAULT 'ai_only',
    agents_json TEXT NOT NULL DEFAULT '[]',
    error_message TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- 辩论消息表
CREATE TABLE IF NOT EXISTS debate_messages (
    id          SERIAL PRIMARY KEY,
    debate_id   TEXT REFERENCES debates(id) ON DELETE CASCADE,
    agent_name  TEXT NOT NULL,
    round_num   SMALLINT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_debate ON debate_messages(debate_id, round_num);

-- 用户 profiles（扩展 Supabase auth.users）
CREATE TABLE IF NOT EXISTS profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username    TEXT UNIQUE NOT NULL,
    avatar_url  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 评论表
CREATE TABLE IF NOT EXISTS comments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id   TEXT REFERENCES debates(id) ON DELETE CASCADE,
    user_id     UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    content     TEXT NOT NULL,
    parent_id   UUID REFERENCES comments(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 模板表
CREATE TABLE IF NOT EXISTS templates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id  UUID REFERENCES auth.users(id),
    name        TEXT NOT NULL,
    description TEXT,
    is_public   BOOLEAN DEFAULT TRUE,
    agents_json JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
