"""Review session, document, progress, SSE, evidence, and report APIs."""

import asyncio
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.sse_manager import sse_manager
from app.db.database import async_session, get_db
from app.db.models import EvidenceItem, OrganizationMember, ReviewDocument, ReviewEvent, ReviewOutput, ReviewReport, ReviewSession
from app.dependencies import GuestUser, require_user
from app.models.schemas import EvidenceItemResponse, EvidenceSourceItem, HumanReviewRequest, ReviewDetail, ReviewDocumentItem, ReviewEventItem, ReviewOutputItem, ReviewProgress, ReviewSummary, CreateReviewRequest
from app.services.document_service import extract_document_text
from app.services.review_service import run_review_background
from app.services.storage_service import storage_service
from app.services.guest_review_service import guest_review_store

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _safe_filename(raw: str) -> str:
    name = raw.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "_", name).strip(" .")
    return name[:255] or "document"


def _validate_file_signature(filename: str, content: bytes) -> None:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        if not content.startswith(b"%PDF-"):
            raise HTTPException(400, "PDF 文件内容无效")
        return
    if lower.endswith(".docx"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if "word/document.xml" not in archive.namelist() or len(archive.infolist()) > 1000:
                    raise HTTPException(400, "DOCX 文件内容无效")
                if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
                    raise HTTPException(400, "DOCX 解压后体积过大")
        except zipfile.BadZipFile as exc:
            raise HTTPException(400, "DOCX 文件内容无效") from exc
        return
    raise HTTPException(400, "仅支持 PDF 或 DOCX 文件")


async def _read_upload_limited(file: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(400, "文件超过 20 MB 限制")
        chunks.append(chunk)
    return b"".join(chunks)


async def _membership(db: AsyncSession, user_id: str, organization_id: str) -> OrganizationMember:
    member = await db.scalar(select(OrganizationMember).options(selectinload(OrganizationMember.organization)).where(OrganizationMember.user_id == user_id, OrganizationMember.organization_id == organization_id))
    if not member:
        raise HTTPException(404, "资源不存在")
    return member


async def _session(db: AsyncSession, user_id: str, session_id: str) -> ReviewSession:
    result = await db.execute(select(ReviewSession).options(selectinload(ReviewSession.documents), selectinload(ReviewSession.outputs), selectinload(ReviewSession.report), selectinload(ReviewSession.evidence), selectinload(ReviewSession.creator)).where(ReviewSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "评审任务不存在")
    await _membership(db, user_id, session.organization_id)
    return session


def _summary(s: ReviewSession) -> ReviewSummary:
    return ReviewSummary(id=s.id, organization_id=s.organization_id, topic=s.topic, max_round=s.max_round, current_round=s.current_round, current_stage=s.current_stage, status=s.status, document_count=len(s.documents or []), evidence_count=len(s.evidence or []), creator_id=s.creator_id, creator_name=s.creator.display_name if s.creator else None, created_at=str(s.created_at), updated_at=str(s.updated_at or s.created_at))


@router.post("", response_model=ReviewSummary, status_code=201)
async def create_review(req: CreateReviewRequest, background_tasks: BackgroundTasks, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        review = guest_review_store.create(user.id, req.topic, req.max_round)
        return ReviewSummary(**guest_review_store.summary(review))
    await _membership(db, user.id, req.organization_id)
    # Files are uploaded after the session is created, so only reject an
    # explicitly blank topic here. The start endpoint validates that at least
    # one input (topic or document) exists before execution.
    if req.topic is not None and not req.topic.strip():
        raise HTTPException(400, "调研主题不能为空")
    session = ReviewSession(organization_id=req.organization_id, creator_id=user.id, topic=req.topic, max_round=req.max_round, documents=[], evidence=[])
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return ReviewSummary(id=session.id, organization_id=session.organization_id, topic=session.topic, max_round=session.max_round, current_round=0, current_stage="draft", status="draft", document_count=0, evidence_count=0, creator_id=session.creator_id, creator_name=user.display_name, created_at=str(session.created_at), updated_at=str(session.updated_at or session.created_at))


@router.get("", response_model=list[ReviewSummary])
async def list_reviews(organization_id: str, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        return []
    await _membership(db, user.id, organization_id)
    result = await db.execute(select(ReviewSession).options(selectinload(ReviewSession.documents), selectinload(ReviewSession.evidence), selectinload(ReviewSession.creator)).where(ReviewSession.organization_id == organization_id).order_by(ReviewSession.created_at.desc()).limit(100))
    return [_summary(item) for item in result.scalars().all()]


@router.get("/{session_id}", response_model=ReviewDetail)
async def get_review(session_id: str, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        try:
            return ReviewDetail(**guest_review_store.detail(guest_review_store.get(session_id, user.id)))
        except KeyError as exc:
            raise HTTPException(404, "评审任务不存在") from exc
    s = await _session(db, user.id, session_id)
    return ReviewDetail(**_summary(s).model_dump(), documents=[ReviewDocumentItem(id=d.id, filename=d.filename, content_type=d.content_type, size_bytes=d.size_bytes, parse_status=d.parse_status, parse_error=d.parse_error) for d in s.documents], outputs=[ReviewOutputItem(id=o.id, agent_role=o.agent_role, round_num=o.round_num, sequence=o.sequence, content_markdown=o.content_markdown, structured_data=o.structured_data, created_at=str(o.created_at)) for o in s.outputs], report_markdown=s.report.markdown if s.report else None, error_message=s.error_message)


@router.post("/{session_id}/documents", response_model=ReviewDocumentItem, status_code=201)
async def upload_document(session_id: str, file: UploadFile = File(...), user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        try:
            review = guest_review_store.get(session_id, user.id)
        except KeyError as exc:
            raise HTTPException(404, "评审任务不存在") from exc
        if review.status not in {"draft", "failed", "interrupted", "needs_revision"}:
            raise HTTPException(409, "评审已启动，不能再修改输入材料")
        if len(review.documents) >= settings.max_upload_files:
            raise HTTPException(400, f"每个评审最多上传 {settings.max_upload_files} 个文件")
        filename = _safe_filename(file.filename or "document")
        if not filename.lower().endswith((".pdf", ".docx")):
            raise HTTPException(400, "仅支持 PDF 或 DOCX 文件")
        content = await _read_upload_limited(file, settings.max_upload_bytes)
        if not content:
            raise HTTPException(400, "文件为空")
        _validate_file_signature(filename, content)
        try:
            text = await asyncio.to_thread(extract_document_text, filename, content)
        except Exception as exc:
            raise HTTPException(400, "文件解析失败，请确认文件未损坏且未加密") from exc
        if not text:
            raise HTTPException(400, "未能提取文档文字，扫描件暂不支持")
        document = {
            "id": f"guest-doc-{hashlib.sha256(content).hexdigest()[:20]}",
            "filename": filename,
            "content_type": file.content_type or "application/octet-stream",
            "size_bytes": len(content),
            "parse_status": "completed",
            "parse_error": None,
            "extracted_text": text[: settings.max_document_chars],
        }
        review.documents.append(document)
        review.updated_at = datetime.now(timezone.utc).isoformat()
        return ReviewDocumentItem(**{key: document[key] for key in ("id", "filename", "content_type", "size_bytes", "parse_status", "parse_error")})
    session = await _session(db, user.id, session_id)
    session = await db.scalar(select(ReviewSession).options(selectinload(ReviewSession.documents)).where(ReviewSession.id == session_id).with_for_update())
    if not session:
        raise HTTPException(404, "评审任务不存在")
    if session.status not in {"draft", "failed", "interrupted", "needs_revision"}:
        raise HTTPException(409, "评审已启动，不能再修改输入材料")
    if len(session.documents) >= settings.max_upload_files:
        raise HTTPException(400, f"每个评审最多上传 {settings.max_upload_files} 个文件")
    filename = _safe_filename(file.filename or "document")
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(400, "仅支持 PDF 或 DOCX 文件")
    content = await _read_upload_limited(file, settings.max_upload_bytes)
    if not content:
        raise HTTPException(400, "文件为空")
    _validate_file_signature(filename, content)
    try:
        text = await asyncio.to_thread(extract_document_text, filename, content)
    except Exception as exc:
        raise HTTPException(400, "文件解析失败，请确认文件未损坏且未加密") from exc
    if not text:
        raise HTTPException(400, "未能提取文档文字，扫描件暂不支持")
    digest = hashlib.sha256(content).hexdigest()
    path = f"{session.organization_id}/{session.id}/{digest}-{filename}"
    stored = await storage_service.save(path, content, file.content_type or "application/octet-stream")
    document = ReviewDocument(session_id=session.id, filename=filename, content_type=file.content_type or "application/octet-stream", size_bytes=len(content), sha256=digest, storage_path=stored, extracted_text=text[: settings.max_document_chars], parse_status="completed")
    db.add(document)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        try:
            await storage_service.delete(stored)
        except Exception:
            pass
        raise HTTPException(500, "文件记录保存失败，请稍后重试") from exc
    await db.refresh(document)
    return ReviewDocumentItem(id=document.id, filename=document.filename, content_type=document.content_type, size_bytes=document.size_bytes, parse_status=document.parse_status)


@router.post("/{session_id}/start", response_model=ReviewProgress)
async def start_review(session_id: str, background_tasks: BackgroundTasks, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        try:
            review = guest_review_store.get(session_id, user.id)
        except KeyError as exc:
            raise HTTPException(404, "评审任务不存在") from exc
        if not review.topic and not review.documents:
            raise HTTPException(400, "请输入调研主题或上传文档")
        if review.status in {"queued", "running", "awaiting_human"}:
            raise HTTPException(409, "评审已在执行")
        if review.status == "completed":
            raise HTTPException(409, "已完成的评审不能重复启动")
        review.status = "queued"
        review.current_stage = "queued"
        guest_review_store.tasks[review.id] = asyncio.create_task(guest_review_store.run(review))
        return ReviewProgress(session_id=review.id, status=review.status, current_stage=review.current_stage, current_round=review.current_round, max_round=review.max_round, output_count=0, evidence_count=0, report_ready=False)
    session = await _session(db, user.id, session_id)
    if not session.topic and not session.documents:
        raise HTTPException(400, "请输入调研主题或上传文档")
    if session.status in {"queued", "running", "awaiting_human"}:
        raise HTTPException(409, "评审已在执行")
    if session.status == "completed":
        raise HTTPException(409, "已完成的评审不能重复启动")
    previous_status = session.status
    if session.status in {"failed", "interrupted", "needs_revision"}:
        await db.execute(delete(ReviewEvent).where(ReviewEvent.session_id == session.id))
        await db.execute(delete(EvidenceItem).where(EvidenceItem.session_id == session.id))
        await db.execute(delete(ReviewOutput).where(ReviewOutput.session_id == session.id))
        await db.execute(delete(ReviewReport).where(ReviewReport.session_id == session.id))
        session.next_event_sequence = 0
        session.next_output_sequence = 0
        session.current_round = 0
        session.error_message = None
    transitioned = await db.execute(update(ReviewSession).where(ReviewSession.id == session.id, ReviewSession.status == previous_status).values(status="queued", current_stage="queued"))
    if transitioned.rowcount != 1:
        await db.rollback()
        raise HTTPException(409, "评审状态已改变，请刷新后重试")
    await db.commit()
    background_tasks.add_task(run_review_background, session.id)
    return ReviewProgress(session_id=session.id, status="queued", current_stage="queued", current_round=session.current_round, max_round=session.max_round, output_count=0, evidence_count=0, report_ready=False)


@router.get("/{session_id}/progress", response_model=ReviewProgress)
async def review_progress(session_id: str, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        try:
            review = guest_review_store.get(session_id, user.id)
        except KeyError as exc:
            raise HTTPException(404, "评审任务不存在") from exc
        return ReviewProgress(session_id=review.id, status=review.status, current_stage=review.current_stage, current_round=review.current_round, max_round=review.max_round, output_count=len(review.outputs), evidence_count=len(review.evidence), report_ready=bool(review.report_markdown), error_message=review.error_message)
    s = await _session(db, user.id, session_id)
    return ReviewProgress(session_id=s.id, status=s.status, current_stage=s.current_stage, current_round=s.current_round, max_round=s.max_round, output_count=len(s.outputs), evidence_count=len(s.evidence), report_ready=bool(s.report), error_message=s.error_message)


@router.post("/{session_id}/human-review", response_model=ReviewProgress)
async def human_review(session_id: str, req: HumanReviewRequest, background_tasks: BackgroundTasks, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        raise HTTPException(409, "游客体验不支持人工复核，请登录后使用")
    session = await _session(db, user.id, session_id)
    member = await _membership(db, user.id, session.organization_id)
    if session.creator_id != user.id and member.role != "owner":
        raise HTTPException(403, "仅创建者或组织 owner 可进行人工复核")
    if settings.review_runtime.lower() != "langgraph":
        raise HTTPException(409, "当前运行时不需要人工复核")
    if session.status != "awaiting_human":
        raise HTTPException(409, "评审当前不在人工复核阶段")
    transitioned = await db.execute(update(ReviewSession).where(ReviewSession.id == session.id, ReviewSession.status == "awaiting_human").values(status="queued"))
    if transitioned.rowcount != 1:
        await db.rollback()
        raise HTTPException(409, "人工复核状态已改变，请刷新后重试")
    await db.commit()
    from app.runtime.langgraph_runtime import resume_langgraph_review

    background_tasks.add_task(resume_langgraph_review, session.id, req.approved, req.note)
    return ReviewProgress(session_id=session.id, status=session.status, current_stage=session.current_stage, current_round=session.current_round, max_round=session.max_round, output_count=len(session.outputs), evidence_count=len(session.evidence), report_ready=bool(session.report), error_message=session.error_message)


@router.get("/{session_id}/events", response_model=list[ReviewEventItem])
async def review_events(session_id: str, after: int = 0, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        try:
            review = guest_review_store.get(session_id, user.id)
        except KeyError as exc:
            raise HTTPException(404, "评审任务不存在") from exc
        return [ReviewEventItem(session_id=review.id, sequence=0, timestamp=review.updated_at, type="session_status", payload={"status": review.status, "stage": review.current_stage, "round": review.current_round})] if after == 0 else []
    await _session(db, user.id, session_id)
    result = await db.execute(select(ReviewEvent).where(ReviewEvent.session_id == session_id, ReviewEvent.sequence > after).order_by(ReviewEvent.sequence))
    return [ReviewEventItem(session_id=e.session_id, sequence=e.sequence, timestamp=str(e.created_at), type=e.event_type, payload=e.payload) for e in result.scalars().all()]


@router.get("/{session_id}/stream")
async def stream_review(session_id: str, last_event_id: int = Header(default=0, alias="Last-Event-ID"), user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        try:
            guest_review_store.get(session_id, user.id)
        except KeyError as exc:
            raise HTTPException(404, "评审任务不存在") from exc
        async def guest_generator():
            queue = await sse_manager.subscribe(session_id, last_event_id)
            try:
                while True:
                    try:
                        raw = await asyncio.wait_for(queue.get(), timeout=25)
                        yield raw
                        if "event: done" in raw:
                            break
                    except asyncio.TimeoutError:
                        yield ":keepalive\n\n"
            finally:
                sse_manager.unsubscribe(session_id, queue)
        return StreamingResponse(guest_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    await _session(db, user.id, session_id)
    async def generator():
        queue = await sse_manager.subscribe(session_id, last_event_id)
        initial = await review_events(session_id, last_event_id, user, db)
        for event in initial:
            data = {"session_id": event.session_id, "sequence": event.sequence, "timestamp": event.timestamp, "type": event.type, **event.payload}
            yield f"id: {event.sequence}\nevent: {event.type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        try:
            while True:
                try:
                    raw = await asyncio.wait_for(queue.get(), timeout=25)
                    yield raw
                    if "event: done" in raw:
                        break
                except asyncio.TimeoutError:
                    yield ":keepalive\n\n"
        finally:
            sse_manager.unsubscribe(session_id, queue)
    return StreamingResponse(generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{session_id}/evidence", response_model=list[EvidenceItemResponse])
async def review_evidence(session_id: str, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        try:
            return [EvidenceItemResponse(**item) for item in guest_review_store.get(session_id, user.id).evidence]
        except KeyError as exc:
            raise HTTPException(404, "评审任务不存在") from exc
    await _session(db, user.id, session_id)
    result = await db.execute(select(EvidenceItem).options(selectinload(EvidenceItem.sources)).where(EvidenceItem.session_id == session_id).order_by(EvidenceItem.created_at))
    return [EvidenceItemResponse(id=e.id, round_num=e.round_num, argument_role=e.argument_role, claim_text=e.claim_text, verdict=e.verdict, rationale=e.rationale, sources=[EvidenceSourceItem(id=s.id, title=s.title, url=s.url, snippet=s.snippet, publisher=s.publisher, retrieved_at=str(s.retrieved_at)) for s in e.sources]) for e in result.scalars().all()]


@router.get("/{session_id}/report")
async def get_report(session_id: str, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        try:
            review = guest_review_store.get(session_id, user.id)
        except KeyError as exc:
            raise HTTPException(404, "评审任务不存在") from exc
        if not review.report_markdown:
            raise HTTPException(404, "评审报告尚未生成")
        return {"session_id": review.id, "markdown": review.report_markdown, "version": 1, "created_at": review.updated_at}
    s = await _session(db, user.id, session_id)
    if not s.report:
        raise HTTPException(404, "评审报告尚未生成")
    return {"session_id": s.id, "markdown": s.report.markdown, "version": s.report.version, "created_at": str(s.report.created_at)}


@router.get("/{session_id}/report.md")
async def download_report(session_id: str, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        try:
            review = guest_review_store.get(session_id, user.id)
        except KeyError as exc:
            raise HTTPException(404, "评审任务不存在") from exc
        if not review.report_markdown:
            raise HTTPException(404, "评审报告尚未生成")
        return Response(review.report_markdown, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="guest-review-{session_id[:8]}.md"'})
    s = await _session(db, user.id, session_id)
    if not s.report:
        raise HTTPException(404, "评审报告尚未生成")
    return Response(s.report.markdown, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="review-{session_id[:8]}.md"'})


@router.delete("/{session_id}", status_code=204)
async def delete_review(session_id: str, user=Depends(require_user), db: AsyncSession = Depends(get_db)):
    if isinstance(user, GuestUser):
        try:
            guest_review_store.get(session_id, user.id)
        except KeyError as exc:
            raise HTTPException(404, "评审任务不存在") from exc
        guest_review_store.reviews.pop(session_id, None)
        task = guest_review_store.tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
        return Response(status_code=204)
    session = await _session(db, user.id, session_id)
    session = await db.scalar(select(ReviewSession).options(selectinload(ReviewSession.documents)).where(ReviewSession.id == session_id).with_for_update())
    if not session:
        raise HTTPException(404, "评审任务不存在")
    member = await _membership(db, user.id, session.organization_id)
    if session.creator_id != user.id and member.role != "owner":
        raise HTTPException(403, "仅创建者或组织 owner 可删除")
    if session.status in {"queued", "running", "awaiting_human"}:
        raise HTTPException(409, "评审执行中，暂不能删除")
    for document in session.documents:
        try:
            await storage_service.delete(document.storage_path)
        except Exception as exc:
            raise HTTPException(502, f"原文件删除失败，请稍后重试: {exc}") from exc
    await db.delete(session)
    await db.commit()
