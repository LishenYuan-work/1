"""Pydantic 请求/响应模型"""

from pydantic import BaseModel, Field


# ========== Agent 角色 ==========
class AgentConfig(BaseModel):
    name: str
    role: str
    stance: str = ""


# ========== 认证 ==========
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    email: str | None = None
    display_name: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserProfile"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    id: str
    username: str
    display_name: str | None
    email: str | None
    created_at: str


# ========== 辩论请求 ==========
class CreateDebateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500, description="辩论话题")
    agents: list[AgentConfig] = Field(..., min_length=2, max_length=8, description="角色列表")
    rounds: int = Field(default=3, ge=2, le=10, description="辩论轮次")
    mode: str = Field(default="ai_only", pattern="^(ai_only|human_mixed)$")
    visibility: str = Field(default="public", pattern="^(public|private)$")


# ========== 辩论响应 ==========
class DebateSummary(BaseModel):
    id: str
    topic: str
    rounds: int
    status: str
    mode: str
    visibility: str
    agents: list[AgentConfig]
    message_count: int
    creator_name: str | None = None
    created_at: str


class DebateDetail(DebateSummary):
    messages: list["MessageItem"]
    error_message: str | None = None
    completed_at: str | None = None


class MessageItem(BaseModel):
    agent_name: str
    content: str
    round_num: int


# ========== 追问请求 ==========
class FollowUpRequest(BaseModel):
    message_index: int = Field(..., ge=0, description="追问第几条发言")
    question: str = Field(..., min_length=1, max_length=1000)


# ========== AI 推荐请求 ==========
class RecommendRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)


class RecommendResponse(BaseModel):
    agents: list[AgentConfig]


# ========== 评论 ==========
class CreateCommentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: int | None = None  # 回复某条评论


class CommentItem(BaseModel):
    id: int
    debate_id: str
    user_id: str | None
    username: str | None = None
    content: str
    parent_id: int | None
    replies: list["CommentItem"] = []
    created_at: str


# ========== 通用 ==========
class ErrorResponse(BaseModel):
    detail: str
