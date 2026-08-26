"""LangGraph runtime adapter for the review workflow.

The graph calls the existing review services for model access, persistence,
search, and SSE emission. LangGraph owns ordering, checkpointing, and human
approval while the public API remains unchanged.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.database import async_session
from app.db.models import ReviewSession
from app.core.config import settings
from app.services.review_service import emit


class ReviewState(TypedDict, total=False):
    topic: str
    doc_content: str
    max_round: int
    current_round: int
    history: list[dict[str, Any]]
    evidence_pool: list[dict[str, Any]]
    session_id: str
    last_output_id: str
    last_agent: str
    human_approved: bool
    human_rejected: bool
    human_note: str


_graph = None
_graph_lock = asyncio.Lock()


def _checkpointer():
    # Local SQLite uses an in-memory checkpoint. PostgreSQL deployments can
    # replace this factory with AsyncPostgresSaver without changing node APIs.
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()


def build_review_graph(checkpointer=None):
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError("安装 langgraph 后才能启用 REVIEW_RUNTIME=langgraph") from exc

    from app.runtime.langgraph_nodes import (
        benefit_argument_node,
        document_parse_node,
        fact_check_node,
        human_review_node,
        risk_argument_node,
        summary_report_node,
    )

    graph = StateGraph(ReviewState)
    for name, node in {
        "document_parse_node": document_parse_node,
        "benefit_argument_node": benefit_argument_node,
        "risk_argument_node": risk_argument_node,
        "fact_check_node": fact_check_node,
        "human_review_node": human_review_node,
        "summary_report_node": summary_report_node,
    }.items():
        graph.add_node(name, node)
    graph.add_edge(START, "document_parse_node")
    graph.add_edge("document_parse_node", "benefit_argument_node")
    graph.add_edge("benefit_argument_node", "fact_check_node")

    def next_after_fact_check(state: ReviewState):
        if state.get("last_agent") == "benefit_argument":
            return "risk_argument_node"
        if state.get("current_round", 0) >= state.get("max_round", 1):
            return "human_review_node"
        return "benefit_argument_node"

    graph.add_conditional_edges("fact_check_node", next_after_fact_check)
    graph.add_edge("risk_argument_node", "fact_check_node")
    def after_human_review(state: ReviewState):
        if state.get("human_approved"):
            return "summary_report_node"
        if state.get("human_rejected"):
            return END
        return "human_review_node"

    graph.add_conditional_edges("human_review_node", after_human_review)
    graph.add_edge("summary_report_node", END)
    return graph.compile(checkpointer=checkpointer or _checkpointer())


async def _get_graph():
    global _graph
    if _graph is None:
        async with _graph_lock:
            if _graph is None:
                _graph = build_review_graph()
    return _graph


async def run_langgraph_review_background(session_id: str) -> None:
    async with async_session() as db:
        session = await db.scalar(select(ReviewSession).options(selectinload(ReviewSession.documents)).where(ReviewSession.id == session_id))
        if not session:
            return
        initial: ReviewState = {
            "topic": session.topic or "",
            "doc_content": "",
            "max_round": session.max_round,
            "current_round": 0,
            "history": [],
            "evidence_pool": [],
            "session_id": session.id,
        }
    try:
        if settings.database_url.startswith("postgresql"):
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            conn_string = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
            async with AsyncPostgresSaver.from_conn_string(conn_string) as saver:
                await saver.setup()
                await build_review_graph(saver).ainvoke(initial, config={"configurable": {"thread_id": session_id}})
        else:
            await (await _get_graph()).ainvoke(initial, config={"configurable": {"thread_id": session_id}})
    except Exception as exc:
        if exc.__class__.__name__ == "GraphInterrupt":
            return
        async with async_session() as db:
            session = await db.get(ReviewSession, session_id)
            if session:
                session.status = "failed"
                session.current_stage = "failed"
                session.error_message = str(exc)
                await db.commit()
                await emit(db, session, "error", {"message": "LangGraph 评审执行失败，请稍后重试。"})
                await emit(db, session, "done", {"status": "failed"})


async def resume_langgraph_review(session_id: str, approved: bool, note: str | None = None) -> None:
    try:
        from langgraph.types import Command
        command = Command(resume={"approved": approved, "note": note or ""})
        if settings.database_url.startswith("postgresql"):
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            conn_string = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
            async with AsyncPostgresSaver.from_conn_string(conn_string) as saver:
                await saver.setup()
                await build_review_graph(saver).ainvoke(command, config={"configurable": {"thread_id": session_id}})
        else:
            await (await _get_graph()).ainvoke(command, config={"configurable": {"thread_id": session_id}})
    except Exception as exc:
        async with async_session() as db:
            session = await db.get(ReviewSession, session_id)
            if session:
                session.status, session.current_stage, session.error_message = "failed", "failed", str(exc)
                await db.commit()
                await emit(db, session, "error", {"message": "人工复核恢复失败，请重新运行评审。"})
                await emit(db, session, "done", {"status": "failed"})
