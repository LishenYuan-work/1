"""辩论路由：CRUD + SSE 流式 + 追问"""

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db, async_session
from app.db.models import Debate, DebateMessage as DebateMessageModel, User
from app.dependencies import get_current_user, require_user
from app.models.schemas import (
    CreateDebateRequest,
    DebateDetail,
    DebateSummary,
    FollowUpRequest,
    MessageItem,
    AgentConfig,
    ErrorResponse,
)
from app.core.sse_manager import sse_manager
from app.services.debate_service import run_debate_background, run_followup

router = APIRouter(prefix="/api/debates", tags=["debates"])


# ========== 辅助函数 ==========

def _debate_to_summary(d: Debate, msg_count: int | None = None) -> DebateSummary:
    agents = json.loads(d.agents_json)
    if msg_count is None:
        msg_count = len(d.messages) if d.messages else 0
    creator_name = d.creator.display_name if d.creator else None
    return DebateSummary(
        id=d.id,
        topic=d.topic,
        rounds=d.rounds,
        status=d.status,
        mode=d.mode,
        visibility=d.visibility,
        agents=[AgentConfig(**a) for a in agents],
        message_count=msg_count,
        creator_name=creator_name,
        created_at=str(d.created_at),
    )


def _debate_to_detail(d: Debate) -> DebateDetail:
    agents = json.loads(d.agents_json)
    messages = [
        MessageItem(agent_name=m.agent_name, content=m.content, round_num=m.round_num)
        for m in (d.messages or [])
    ]
    creator_name = d.creator.display_name if d.creator else None
    return DebateDetail(
        id=d.id,
        topic=d.topic,
        rounds=d.rounds,
        status=d.status,
        mode=d.mode,
        visibility=d.visibility,
        agents=[AgentConfig(**a) for a in agents],
        message_count=len(messages),
        messages=messages,
        creator_name=creator_name,
        error_message=d.error_message,
        completed_at=str(d.completed_at) if d.completed_at else None,
        created_at=str(d.created_at),
    )


# ========== 创建辩论 ==========

@router.post("", response_model=DebateSummary, status_code=201)
async def create_debate(
    req: CreateDebateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """创建新辩论并立即启动后台执行（登录可选）"""
    debate = Debate(
        creator_id=user.id if user else None,
        topic=req.topic,
        rounds=req.rounds,
        mode=req.mode,
        visibility=req.visibility,
        agents_json=json.dumps([a.model_dump() for a in req.agents], ensure_ascii=False),
        status="pending",
    )
    db.add(debate)
    await db.commit()
    await db.refresh(debate)

    # 加载 creator 关系
    if user:
        debate.creator = user

    # 后台异步启动辩论
    background_tasks.add_task(run_debate_background, debate.id, async_session)

    return _debate_to_summary(debate, msg_count=0)


# ========== 辩论列表（公开）==========

@router.get("", response_model=list[DebateSummary])
async def list_debates(
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """获取公开辩论列表"""
    query = (
        select(Debate)
        .options(selectinload(Debate.messages), selectinload(Debate.creator))
        .where(Debate.visibility == "public")
    )
    if status:
        query = query.where(Debate.status == status)
    query = query.order_by(Debate.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    debates = result.unique().scalars().all()
    return [_debate_to_summary(d) for d in debates]


# ========== 我的辩论 ==========

@router.get("/my", response_model=list[DebateSummary])
async def list_my_debates(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """获取当前用户的辩论列表"""
    query = (
        select(Debate)
        .options(selectinload(Debate.messages), selectinload(Debate.creator))
        .where(Debate.creator_id == user.id)
        .order_by(Debate.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    debates = result.unique().scalars().all()
    return [_debate_to_summary(d) for d in debates]


# ========== 辩论详情 ==========

@router.get("/{debate_id}", response_model=DebateDetail)
async def get_debate(debate_id: str, db: AsyncSession = Depends(get_db)):
    """获取辩论详情（含所有已生成的消息）"""
    result = await db.execute(
        select(Debate)
        .options(selectinload(Debate.messages), selectinload(Debate.creator))
        .where(Debate.id == debate_id)
    )
    debate = result.unique().scalar_one_or_none()
    if not debate:
        raise HTTPException(404, "辩论不存在")
    return _debate_to_detail(debate)


# ========== 辩论消息 ==========

@router.get("/{debate_id}/messages", response_model=list[MessageItem])
async def get_debate_messages(debate_id: str, db: AsyncSession = Depends(get_db)):
    """获取某辩论的所有发言"""
    result = await db.execute(
        select(DebateMessageModel)
        .where(DebateMessageModel.debate_id == debate_id)
        .order_by(DebateMessageModel.round_num, DebateMessageModel.created_at)
    )
    messages = result.scalars().all()
    return [MessageItem(agent_name=m.agent_name, content=m.content, round_num=m.round_num) for m in messages]


# ========== 删除辩论 ==========

@router.delete("/{debate_id}", status_code=204)
async def delete_debate(
    debate_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """删除辩论（仅创建者可删）"""
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(404, "辩论不存在")
    if debate.creator_id and debate.creator_id != user.id:
        raise HTTPException(403, "只能删除自己创建的辩论")
    await db.delete(debate)
    await db.commit()


# ========== SSE 流式端点（核心！）==========

@router.get("/{debate_id}/stream")
async def stream_debate(debate_id: str, db: AsyncSession = Depends(get_db)):
    """SSE 实时流式辩论端点"""
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(404, "辩论不存在")

    async def event_generator():
        queue = await sse_manager.subscribe(debate_id)
        try:
            while True:
                try:
                    event_str = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event_str
                except asyncio.TimeoutError:
                    yield ":keepalive\n\n"

                if sse_manager._completed.get(debate_id) and queue.empty():
                    break
        except asyncio.CancelledError:
            pass
        finally:
            sse_manager.unsubscribe(debate_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ========== 追问 ==========

@router.post("/{debate_id}/followup")
async def followup_debate(
    debate_id: str,
    req: FollowUpRequest,
    db: AsyncSession = Depends(get_db),
):
    """追问某条发言"""
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(404, "辩论不存在")

    agents = json.loads(debate.agents_json)
    messages_result = await db.execute(
        select(DebateMessageModel)
        .where(DebateMessageModel.debate_id == debate_id)
        .order_by(DebateMessageModel.round_num, DebateMessageModel.created_at)
    )
    messages = messages_result.scalars().all()

    if req.message_index >= len(messages):
        raise HTTPException(400, "发言序号无效")

    target_msg = messages[req.message_index]
    agent_config = next(
        (a for a in agents if a["name"] == target_msg.agent_name),
        agents[0],
    )

    reply = await run_followup(agent_config, target_msg.content, req.question)
    return {"reply": reply, "agent": target_msg.agent_name}
