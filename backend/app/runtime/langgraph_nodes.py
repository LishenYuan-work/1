"""LangGraph nodes backed by the existing review persistence services."""

from __future__ import annotations

import json
import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.db.database import async_session
from app.db.models import EvidenceItem, ReviewOutput, ReviewReport, ReviewSession
from app.services.review_service import _fallback_report, _normalize_report, emit, fact_check_output, run_node, save_output, update_stage
from app.core.web_search import filter_relevant_results, format_search_results, search_web


def _search_claims(query: str, max_results: int = 3) -> list[dict]:
    return search_web(query, max_results)


try:
    from langchain_core.tools import StructuredTool
    search_claims_tool = StructuredTool.from_function(_search_claims, name="search_web", description="Search public web sources for a factual claim.")
except ImportError:  # pragma: no cover - optional until LangGraph runtime is enabled
    search_claims_tool = _search_claims


def _text_for_session(session: ReviewSession) -> str:
    parts = [session.topic or ""]
    for document in session.documents:
        if document.extracted_text:
            parts.append(f"\n[{document.filename}]\n{document.extracted_text}")
    return "\n".join(parts).strip()


async def document_parse_node(state: dict[str, Any]) -> dict[str, Any]:
    async with async_session() as db:
        session = await db.scalar(select(ReviewSession).options(selectinload(ReviewSession.documents)).where(ReviewSession.id == state["session_id"]))
        if not session:
            raise RuntimeError("评审任务不存在")
        transitioned = await db.execute(update(ReviewSession).where(ReviewSession.id == session.id, ReviewSession.status == "queued").values(status="running", started_at=datetime.now(timezone.utc)))
        if transitioned.rowcount != 1:
            raise RuntimeError("评审状态已改变，拒绝重复启动")
        await db.commit()
        await update_stage(db, session, "document_parse", "running", 0)
        await emit(db, session, "agent_start", {"agent": "document_parse", "round": 0})
        text = _text_for_session(session)
        if not session.documents and session.topic:
            initial_sources = await asyncio.to_thread(search_web, session.topic[:180], 5)
            relevant_sources = filter_relevant_results(session.topic, initial_sources)
            source_text = format_search_results(relevant_sources) if relevant_sources else "（未找到与主题直接相关的公开资料；请仅基于主题生成初步整理，不要因资料为空而报错。）"
            text = f"主题：{session.topic}\n\n初步公开资料：\n{source_text}"
        fallback = {"summary": text[:2000] or "尚未提供文档，以下基于主题进行初步资料整理。", "claims": []}
        parse_messages = [
            {"role": "system", "content": "你是文档解析 Agent。只返回 JSON。没有上传文档或没有相关公开资料时，必须基于主题生成简短 summary，不要返回错误或拒绝继续。"},
            {"role": "user", "content": text[:12000]},
        ]
        try:
            result = await run_node(db, session, "document_parse", parse_messages, fallback)
        except Exception:
            if session.documents or not session.topic:
                raise
            result = fallback
        output = await save_output(db, session, "document_parse", 0, result.get("summary", fallback["summary"]), result)
        return {"doc_content": text, "history": [{"agent": "document_parse", "output_id": output.id}], "topic": session.topic or ""}


async def benefit_argument_node(state: dict[str, Any]) -> dict[str, Any]:
    round_num = max(1, state.get("current_round", 0) + 1)
    async with async_session() as db:
        session = await db.scalar(select(ReviewSession).where(ReviewSession.id == state["session_id"]))
        if not session:
            raise RuntimeError("评审任务不存在")
        await update_stage(db, session, "benefit_argument", "running", round_num)
        await emit(db, session, "agent_start", {"agent": "benefit_argument", "round": round_num})
        fallback = {"summary": "从可行性、收益和有利条件分析该方案。", "claims": ["方案具备潜在实施收益，但仍需结合具体材料验证。"]}
        result = await run_node(db, session, "benefit_argument", [{"role": "system", "content": "你是收益论证 Agent。只返回 JSON，claims 为可核查的事实性论据数组。"}, {"role": "user", "content": json.dumps({"topic": session.topic, "document": state.get("doc_content", ""), "round": round_num}, ensure_ascii=False)}], fallback)
        output = await save_output(db, session, "benefit_argument", round_num, result.get("summary", ""), result)
        return {"current_round": round_num, "last_output_id": output.id, "last_agent": "benefit_argument", "history": [*state.get("history", []), {"agent": "benefit_argument", "round": round_num, "output_id": output.id}]}


async def risk_argument_node(state: dict[str, Any]) -> dict[str, Any]:
    round_num = state.get("current_round", 1)
    async with async_session() as db:
        session = await db.scalar(select(ReviewSession).where(ReviewSession.id == state["session_id"]))
        if not session:
            raise RuntimeError("评审任务不存在")
        await update_stage(db, session, "risk_argument", "running", round_num)
        await emit(db, session, "agent_start", {"agent": "risk_argument", "round": round_num})
        fallback = {"summary": "识别落地约束、潜在风险和反面论据。", "claims": ["方案的落地依赖关键约束条件，现有材料尚不足以排除实施风险。"]}
        result = await run_node(db, session, "risk_argument", [{"role": "system", "content": "你是风险研判 Agent。只返回 JSON，claims 为可核查的事实性论据数组。"}, {"role": "user", "content": json.dumps({"topic": session.topic, "document": state.get("doc_content", ""), "round": round_num}, ensure_ascii=False)}], fallback)
        output = await save_output(db, session, "risk_argument", round_num, result.get("summary", ""), result)
        return {"last_output_id": output.id, "last_agent": "risk_argument", "history": [*state.get("history", []), {"agent": "risk_argument", "round": round_num, "output_id": output.id}]}


async def fact_check_node(state: dict[str, Any]) -> dict[str, Any]:
    async with async_session() as db:
        session = await db.scalar(select(ReviewSession).where(ReviewSession.id == state["session_id"]))
        output = await db.get(ReviewOutput, state["last_output_id"])
        if not session or not output:
            raise RuntimeError("缺少待核查论据")
        await update_stage(db, session, "fact_check", "running", state.get("current_round", 1))
        claims = [item.get("claim", "") if isinstance(item, dict) else str(item) for item in (output.structured_data or {}).get("claims", [])]
        await fact_check_output(db, session, output, state.get("current_round", 1), claims, search_claims_tool)
        evidence = (await db.execute(select(EvidenceItem).where(EvidenceItem.session_id == session.id).order_by(EvidenceItem.created_at))).scalars().all()
        if output.agent_role == "risk_argument":
            await emit(db, session, "round_complete", {"round": state.get("current_round", 1), "max_round": session.max_round})
        return {"evidence_pool": [{"claim": item.claim_text, "verdict": item.verdict} for item in evidence]}


async def human_review_node(state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("human_approved"):
        from langgraph.types import interrupt
        async with async_session() as db:
            session = await db.get(ReviewSession, state["session_id"])
            if session:
                session.status = "awaiting_human"
                session.current_stage = "human_review"
                await db.commit()
                await emit(db, session, "session_status", {"status": "awaiting_human", "stage": "human_review", "round": session.current_round})
        decision = interrupt({"type": "report_review", "session_id": state.get("session_id")})
        approved = bool(decision and decision.get("approved"))
        if not approved:
            async with async_session() as db:
                session = await db.get(ReviewSession, state["session_id"])
                if session:
                    session.status = "needs_revision"
                    session.current_stage = "human_review"
                    session.error_message = (decision or {}).get("note") or "人工复核未通过"
                    await db.commit()
                    await emit(db, session, "done", {"status": "needs_revision"})
        return {"human_approved": approved, "human_rejected": not approved, "human_note": (decision or {}).get("note", "")}
    return {}


async def summary_report_node(state: dict[str, Any]) -> dict[str, Any]:
    async with async_session() as db:
        session = await db.scalar(select(ReviewSession).where(ReviewSession.id == state["session_id"]))
        if not session:
            raise RuntimeError("评审任务不存在")
        await update_stage(db, session, "summary_report", "running", session.max_round)
        await emit(db, session, "agent_start", {"agent": "summary_report", "round": session.max_round})
        outputs = (await db.execute(select(ReviewOutput).where(ReviewOutput.session_id == session.id).order_by(ReviewOutput.sequence))).scalars().all()
        evidence = (await db.execute(select(EvidenceItem).options(selectinload(EvidenceItem.sources)).where(EvidenceItem.session_id == session.id))).scalars().all()
        fallback = {"markdown": _fallback_report(session, outputs, evidence)}
        result = await run_node(db, session, "summary_report", [{"role": "system", "content": "你是汇总评审 Agent。输出 JSON，markdown 必须严格包含五个指定二级标题。"}, {"role": "user", "content": json.dumps({"topic": session.topic, "outputs": [item.content_markdown for item in outputs], "evidence": [item.claim_text for item in evidence]}, ensure_ascii=False)}], fallback)
        markdown = _normalize_report(result.get("markdown", fallback["markdown"]))
        await save_output(db, session, "summary_report", session.max_round, markdown, result)
        db.add(ReviewReport(session_id=session.id, markdown=markdown))
        session.status, session.current_stage, session.completed_at = "completed", "completed", datetime.now(timezone.utc)
        await db.commit()
        await emit(db, session, "report_ready", {"markdown": markdown})
        await emit(db, session, "done", {"status": "completed"})
        return {"history": [*state.get("history", []), {"agent": "summary_report"}], "human_approved": True}
