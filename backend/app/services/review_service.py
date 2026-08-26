"""Self-managed review workflow used before the LangGraph runtime migration."""

import asyncio
import json
import re
import time
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.concurrency import review_limit
from app.core.config import settings
from app.core.sse_manager import sse_manager
from app.core.web_search import format_search_results, search_web
from app.db.database import async_session
from app.db.models import EvidenceItem, EvidenceSource, ReviewEvent, ReviewOutput, ReviewReport, ReviewSession, ReviewTrace
from app.services.llm_service import chat, structured

AGENTS = {
    "document_parse": "文档解析 Agent",
    "benefit_argument": "收益论证 Agent",
    "risk_argument": "风险研判 Agent",
    "fact_check": "事实核查 Agent",
    "summary_report": "汇总评审 Agent",
}
REPORT_HEADINGS = ["## 方案概述", "## 收益清单", "## 风险与隐患清单", "## 待确认不确定性点", "## 参考证据来源列表"]


async def emit(db, session: ReviewSession, event_type: str, payload: dict) -> None:
    next_sequence = await db.scalar(update(ReviewSession).where(ReviewSession.id == session.id).values(next_event_sequence=ReviewSession.next_event_sequence + 1).returning(ReviewSession.next_event_sequence))
    event = ReviewEvent(session_id=session.id, sequence=int(next_sequence or 1), event_type=event_type, payload=payload)
    db.add(event)
    await db.commit()
    data = {"session_id": session.id, "sequence": event.sequence, "timestamp": datetime.now(timezone.utc).isoformat(), "type": event_type, **payload}
    await sse_manager.broadcast(session.id, event_type, data)


async def update_stage(db, session: ReviewSession, stage: str, status: str | None = None, round_num: int | None = None) -> None:
    session.current_stage = stage
    if status:
        session.status = status
    if round_num is not None:
        session.current_round = round_num
    await db.commit()
    await emit(db, session, "session_status", {"status": session.status, "stage": stage, "round": session.current_round})


async def run_node(db, session: ReviewSession, node_name: str, messages: list[dict[str, str]], fallback: dict) -> dict:
    started = time.perf_counter()
    pending_chunks: list[str] = []
    pending_size = 0

    async def flush_chunks() -> None:
        nonlocal pending_size
        if pending_chunks:
            content = "".join(pending_chunks)
            pending_chunks.clear()
            pending_size = 0
            await emit(db, session, "agent_chunk", {"agent": node_name, "round": session.current_round, "content": content})

    try:
        async def on_chunk(chunk: str) -> None:
            nonlocal pending_size
            pending_chunks.append(chunk)
            pending_size += len(chunk)
            if pending_size >= 512:
                await flush_chunks()

        result = await structured(messages, fallback, on_chunk=on_chunk)
        await flush_chunks()
        _validate_node_result(node_name, result)
        db.add(ReviewTrace(session_id=session.id, node_name=node_name, duration_ms=int((time.perf_counter() - started) * 1000), prompt_tokens=sum(len(message.get("content", "")) for message in messages) // 4, completion_tokens=len(json.dumps(result, ensure_ascii=False)) // 4, model=settings.deepseek_model, status="completed"))
        await db.commit()
        return result
    except Exception as exc:
        await flush_chunks()
        db.add(ReviewTrace(session_id=session.id, node_name=node_name, duration_ms=int((time.perf_counter() - started) * 1000), model=settings.deepseek_model, status="failed", error_message=str(exc)))
        await db.commit()
        raise


def _validate_node_result(node_name: str, result: dict) -> None:
    if node_name == "summary_report":
        if not isinstance(result.get("markdown"), str) or not result["markdown"].strip():
            raise ValueError("汇总 Agent 未返回 markdown 报告")
        return
    if not isinstance(result.get("summary"), str) or not result["summary"].strip():
        raise ValueError(f"{node_name} 未返回有效 summary")
    claims = result.get("claims", [])
    if not isinstance(claims, list) or len(claims) > 50:
        raise ValueError(f"{node_name} claims 必须是最多 50 条的数组")
    if node_name in {"benefit_argument", "risk_argument"} and not claims:
        raise ValueError(f"{node_name} 至少需要一条论据")
    for claim in claims:
        value = claim.get("claim") if isinstance(claim, dict) else claim
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{node_name} 包含空论据")


async def save_output(db, session: ReviewSession, role: str, round_num: int, content: str, structured_data: dict | None = None) -> ReviewOutput:
    sequence = int(await db.scalar(update(ReviewSession).where(ReviewSession.id == session.id).values(next_output_sequence=ReviewSession.next_output_sequence + 1).returning(ReviewSession.next_output_sequence)) or 1)
    output = ReviewOutput(session_id=session.id, agent_role=role, round_num=round_num, sequence=sequence, content_markdown=content, structured_data=structured_data)
    db.add(output)
    await db.commit()
    await emit(db, session, "agent_result", {"agent": role, "round": round_num, "output_id": output.id, "content": content, "structured_data": structured_data or {}})
    return output


def _text_for_session(session: ReviewSession) -> str:
    parts = [session.topic or ""]
    for document in session.documents:
        if document.extracted_text:
            parts.append(f"\n[{document.filename}]\n{document.extracted_text}")
    return "\n".join(parts).strip()


async def fact_check_output(db, session: ReviewSession, output: ReviewOutput, round_num: int, claims: list[str], searcher=search_web) -> None:
    await emit(db, session, "agent_start", {"agent": "fact_check", "round": round_num})
    for claim in claims:
        if not claim.strip():
            continue
        await emit(db, session, "evidence_upsert", {"agent": "fact_check", "round": round_num, "claim": claim, "status": "checking"})
        if hasattr(searcher, "invoke"):
            results = await asyncio.to_thread(searcher.invoke, {"query": claim[:180], "max_results": 3})
        else:
            results = await asyncio.to_thread(searcher, claim[:180], 3)
        verdict, rationale = await _classify_claim(claim, results)
        evidence = EvidenceItem(session_id=session.id, output_id=output.id, round_num=round_num, argument_role=output.agent_role, claim_text=claim, verdict=verdict, rationale=rationale)
        db.add(evidence)
        await db.flush()
        for result in results:
            if result.get("url", "").startswith(("http://", "https://")):
                db.add(EvidenceSource(evidence_id=evidence.id, title=result.get("title", "检索来源"), url=result["url"], snippet=result.get("body")))
        await db.commit()
        await emit(db, session, "evidence_upsert", {"agent": "fact_check", "round": round_num, "evidence_id": evidence.id, "claim": claim, "verdict": verdict, "source_count": sum(1 for item in results if item.get("url", "").startswith(("http://", "https://")))})


async def _classify_claim(claim: str, results: list[dict]) -> tuple[str, str]:
    usable = [item for item in results if item.get("url", "").startswith(("http://", "https://"))]
    if not usable:
        return "uncertain", "未检索到带链接的可靠公开来源，保留不确定性。"
    try:
        result = await structured([
            {"role": "system", "content": "你是事实核查 Agent。仅根据给定来源判断论据。只能返回 JSON：verdict 必须是 verified、contradicted 或 uncertain；没有直接支持时不得判定 verified，不得凭空补充信息。"},
            {"role": "user", "content": json.dumps({"claim": claim, "sources": [{"title": item.get("title", ""), "snippet": item.get("body", "")[:500], "url": item["url"]} for item in usable]}, ensure_ascii=False)},
        ], {"verdict": "uncertain", "rationale": "搜索结果未能证明或反驳该论据。"})
    except Exception:
        return "uncertain", "事实核查模型未能完成判断，保留不确定性。"
    verdict = result.get("verdict")
    rationale = result.get("rationale")
    if verdict not in {"verified", "contradicted", "uncertain"} or not isinstance(rationale, str) or not rationale.strip():
        return "uncertain", "搜索结果未能证明或反驳该论据。"
    return verdict, rationale[:2000]


async def run_review_background(session_id: str) -> None:
    if settings.review_runtime.lower() == "langgraph":
        from app.runtime.langgraph_runtime import run_langgraph_review_background
        await review_limit.acquire(session_id)
        try:
            await run_langgraph_review_background(session_id)
        finally:
            review_limit.release(session_id)
        return
    await review_limit.acquire(session_id)
    try:
        async with async_session() as db:
            session = await db.scalar(select(ReviewSession).options(selectinload(ReviewSession.documents)).where(ReviewSession.id == session_id))
            if not session:
                return
            transitioned = await db.execute(update(ReviewSession).where(ReviewSession.id == session.id, ReviewSession.status == "queued").values(status="running", started_at=datetime.now(timezone.utc)))
            if transitioned.rowcount != 1:
                return
            await db.commit()
            try:
                await update_stage(db, session, "document_parse", "running")
                await emit(db, session, "agent_start", {"agent": "document_parse", "round": 0})
                text = _text_for_session(session)
                if not session.documents and session.topic:
                    initial_sources = await asyncio.to_thread(search_web, session.topic[:180], 5)
                    text = f"主题：{session.topic}\n\n初步公开资料：\n{format_search_results(initial_sources)}"
                fallback_doc = {"summary": text[:2000] or "尚未提供文档，以下基于主题进行初步资料整理。", "claims": []}
                doc = await run_node(db, session, "document_parse", [{"role": "system", "content": "你是文档解析 Agent。只返回 JSON。"}, {"role": "user", "content": text[:12000]}], fallback_doc)
                await save_output(db, session, "document_parse", 0, doc.get("summary", fallback_doc["summary"]), doc)
                for round_num in range(1, session.max_round + 1):
                    await update_stage(db, session, "benefit_argument", "running", round_num)
                    await emit(db, session, "agent_start", {"agent": "benefit_argument", "round": round_num})
                    benefit_fallback = {"summary": "从可行性、收益和有利条件分析该方案。", "claims": ["方案具备潜在实施收益，但仍需结合具体材料验证。"]}
                    benefit = await run_node(db, session, "benefit_argument", [{"role": "system", "content": "你是收益论证 Agent。只返回 JSON，claims 为可核查的事实性论据数组。"}, {"role": "user", "content": json.dumps({"topic": session.topic, "document": doc, "round": round_num}, ensure_ascii=False)}], benefit_fallback)
                    benefit_output = await save_output(db, session, "benefit_argument", round_num, benefit.get("summary", ""), benefit)
                    await fact_check_output(db, session, benefit_output, round_num, [c.get("claim", "") if isinstance(c, dict) else str(c) for c in benefit.get("claims", [])])
                    await update_stage(db, session, "risk_argument", "running", round_num)
                    await emit(db, session, "agent_start", {"agent": "risk_argument", "round": round_num})
                    risk_fallback = {"summary": "识别落地约束、潜在风险和反面论据。", "claims": ["方案的落地依赖关键约束条件，现有材料尚不足以排除实施风险。"]}
                    risk = await run_node(db, session, "risk_argument", [{"role": "system", "content": "你是风险研判 Agent。只返回 JSON，claims 为可核查的事实性论据数组。"}, {"role": "user", "content": json.dumps({"topic": session.topic, "document": doc, "benefit": benefit, "round": round_num}, ensure_ascii=False)}], risk_fallback)
                    risk_output = await save_output(db, session, "risk_argument", round_num, risk.get("summary", ""), risk)
                    await fact_check_output(db, session, risk_output, round_num, [c.get("claim", "") if isinstance(c, dict) else str(c) for c in risk.get("claims", [])])
                    await emit(db, session, "round_complete", {"round": round_num, "max_round": session.max_round})
                await update_stage(db, session, "summary_report", "running", session.max_round)
                await emit(db, session, "agent_start", {"agent": "summary_report", "round": session.max_round})
                outputs = (await db.execute(select(ReviewOutput).where(ReviewOutput.session_id == session.id).order_by(ReviewOutput.sequence))).scalars().all()
                evidence = (await db.execute(select(EvidenceItem).options(selectinload(EvidenceItem.sources)).where(EvidenceItem.session_id == session.id))).scalars().all()
                report_fallback = {"markdown": _fallback_report(session, outputs, evidence)}
                evidence_payload = []
                for item in evidence:
                    sources = (await db.execute(select(EvidenceSource).where(EvidenceSource.evidence_id == item.id))).scalars().all()
                    evidence_payload.append({"claim": item.claim_text, "verdict": item.verdict, "rationale": item.rationale, "sources": [{"title": source.title, "url": source.url} for source in sources]})
                summary = await run_node(db, session, "summary_report", [{"role": "system", "content": "你是汇总评审 Agent。只能使用给定输出和证据，禁止编造来源。输出 JSON，markdown 必须严格按给定五个标题和顺序。"}, {"role": "user", "content": json.dumps({"topic": session.topic, "outputs": [o.content_markdown for o in outputs], "evidence": evidence_payload}, ensure_ascii=False)}], report_fallback)
                markdown = _normalize_report(summary["markdown"], session, evidence)
                db.add(ReviewReport(session_id=session.id, markdown=markdown))
                session.status, session.current_stage, session.completed_at = "completed", "completed", datetime.now(timezone.utc)
                await db.commit()
                await emit(db, session, "report_ready", {"markdown": markdown})
                await emit(db, session, "done", {"status": "completed"})
            except Exception as exc:
                session.status, session.error_message = "failed", str(exc)
                await db.commit()
                await emit(db, session, "error", {"message": "评审执行失败，请稍后重试。"})
                await emit(db, session, "done", {"status": "failed"})
    finally:
        review_limit.release(session_id)


def _fallback_report(session: ReviewSession, outputs: list[ReviewOutput], evidence: list[EvidenceItem]) -> str:
    benefits = [o.content_markdown for o in outputs if o.agent_role == "benefit_argument"]
    risks = [o.content_markdown for o in outputs if o.agent_role == "risk_argument"]
    uncertain = [e.claim_text for e in evidence if e.verdict == "uncertain"]
    sources = []
    for item in evidence:
        links = ", ".join(f"[{source.title}]({source.url})" for source in item.sources if source.url)
        sources.append(f"- {item.claim_text}（{item.verdict}）" + (f"：{links}" if links else ""))
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "- 暂无"
    return "\n\n".join([
        "## 方案概述\n" + (session.topic or "未命名评审"),
        "## 收益清单\n" + bullets(benefits),
        "## 风险与隐患清单\n" + bullets(risks),
        "## 待确认不确定性点\n" + bullets(uncertain),
        "## 参考证据来源列表\n" + bullets(sources),
    ])


def _normalize_report(markdown: str, session: ReviewSession | None = None, evidence: list[EvidenceItem] | None = None) -> str:
    sections: dict[str, str] = {}
    current: str | None = None
    for line in markdown.splitlines():
        heading = line.strip()
        if heading in REPORT_HEADINGS:
            current = heading
            sections.setdefault(heading, "")
        elif current:
            sections[current] += line + "\n"
    fallback = {
        "## 方案概述": session.topic if session and session.topic else "未命名评审",
        "## 收益清单": "- 暂无",
        "## 风险与隐患清单": "- 暂无",
        "## 待确认不确定性点": "- 暂无",
        "## 参考证据来源列表": "- 暂无",
    }
    if evidence:
        fallback["## 待确认不确定性点"] = "\n".join(f"- {item.claim_text}" for item in evidence if item.verdict == "uncertain") or "- 暂无"
        source_lines = []
        for item in evidence:
            links = ", ".join(f"[{source.title}]({source.url})" for source in item.sources if source.url)
            source_lines.append(f"- {item.claim_text}（{item.verdict}）" + (f"：{links}" if links else ""))
        fallback["## 参考证据来源列表"] = "\n".join(source_lines) or "- 暂无"
        sections["## 参考证据来源列表"] = fallback["## 参考证据来源列表"]
    return "\n\n".join(f"{heading}\n{(sections.get(heading) or fallback[heading]).strip()}" for heading in REPORT_HEADINGS)
