"""Pydantic request and response contracts."""

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class OrganizationSummary(BaseModel):
    id: str
    name: str
    role: str


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: str | None
    email_verified: bool
    organizations: list[OrganizationSummary] = []
    created_at: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)
    organization_name: str | None = Field(default=None, min_length=2, max_length=120)
    invite_token: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = True


class TokenResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserProfile


class SupabaseExchangeRequest(BaseModel):
    access_token: str = Field(min_length=20)
    display_name: str | None = Field(default=None, max_length=100)
    organization_name: str | None = Field(default=None, min_length=2, max_length=120)
    invite_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class TokenRequest(BaseModel):
    token: str


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class InviteMemberRequest(BaseModel):
    email: EmailStr


class MemberItem(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    role: str
    joined_at: str


class CreateReviewRequest(BaseModel):
    organization_id: str
    topic: str | None = Field(default=None, max_length=2000)
    max_round: int = Field(default=3, ge=1, le=5)


class UpdateReviewRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=2000)
    max_round: int | None = Field(default=None, ge=1, le=5)


class ReviewDocumentItem(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    parse_status: str
    parse_error: str | None = None


class ReviewOutputItem(BaseModel):
    id: str
    agent_role: str
    round_num: int
    sequence: int
    content_markdown: str
    structured_data: dict[str, Any] | None = None
    created_at: str


class EvidenceSourceItem(BaseModel):
    id: str
    title: str
    url: str
    snippet: str | None
    publisher: str | None
    retrieved_at: str


class EvidenceItemResponse(BaseModel):
    id: str
    round_num: int
    argument_role: str
    claim_text: str
    verdict: Literal["verified", "contradicted", "uncertain"]
    rationale: str
    sources: list[EvidenceSourceItem]


class ReviewSummary(BaseModel):
    id: str
    organization_id: str
    topic: str | None
    max_round: int
    current_round: int
    current_stage: str
    status: str
    document_count: int
    evidence_count: int
    creator_id: str
    creator_name: str | None
    created_at: str
    updated_at: str


class ReviewDetail(ReviewSummary):
    documents: list[ReviewDocumentItem]
    outputs: list[ReviewOutputItem]
    report_markdown: str | None = None
    error_message: str | None = None


class ReviewProgress(BaseModel):
    session_id: str
    status: str
    current_stage: str
    current_round: int
    max_round: int
    output_count: int
    evidence_count: int
    report_ready: bool
    error_message: str | None = None


class ReviewEventItem(BaseModel):
    session_id: str
    sequence: int
    timestamp: str
    type: str
    payload: dict[str, Any]


class HumanReviewRequest(BaseModel):
    approved: bool
    note: str | None = Field(default=None, max_length=2000)


class ClaimPayload(BaseModel):
    claim: str = Field(min_length=1)


class ArgumentPayload(BaseModel):
    summary: str
    claims: list[ClaimPayload]

    @model_validator(mode="after")
    def require_claims(self):
        if not self.claims:
            raise ValueError("at least one claim is required")
        return self
