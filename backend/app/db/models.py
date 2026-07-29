"""SQLAlchemy ORM 模型"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ========== 用户资料表 ==========
class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    phone: Mapped[str] = mapped_column(String(11), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关联
    debates: Mapped[list["Debate"]] = relationship("Debate", back_populates="creator")


# ========== 辩论表 ==========
class Debate(Base):
    __tablename__ = "debates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    creator_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    rounds: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="public")
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="ai_only")

    agents_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关联
    creator: Mapped["Profile | None"] = relationship("Profile", back_populates="debates")
    messages: Mapped[list["DebateMessage"]] = relationship(
        "DebateMessage", back_populates="debate", cascade="all, delete-orphan",
        order_by="DebateMessage.round_num, DebateMessage.created_at"
    )


# ========== 辩论消息表 ==========
class DebateMessage(Base):
    __tablename__ = "debate_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    debate_id: Mapped[str] = mapped_column(String(36), ForeignKey("debates.id", ondelete="CASCADE"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(200), nullable=False)
    round_num: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    debate: Mapped["Debate"] = relationship("Debate", back_populates="messages")


# ========== 评论表 ==========
class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    debate_id: Mapped[str] = mapped_column(String(36), ForeignKey("debates.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关联
    user: Mapped["Profile | None"] = relationship("Profile")
    parent: Mapped["Comment | None"] = relationship(
        "Comment", back_populates="replies", remote_side="Comment.id"
    )
    replies: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="parent", cascade="all, delete-orphan"
    )
