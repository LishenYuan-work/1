"""事实核查路由 — 文本提交 + 文件上传"""

import io
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from app.db.database import async_session
from app.db.models import Debate
from app.services.fact_check_service import run_fact_check

router = APIRouter(prefix="/api/fact-check", tags=["fact-check"])

MAX_TEXT_LENGTH = 10000  # 最大文本长度


class FactCheckRequest(BaseModel):
    text: str = Field(..., min_length=50, max_length=MAX_TEXT_LENGTH, description="需要审查的文本")


def _extract_text_from_pdf(content: bytes) -> str:
    """从 PDF 中提取文本"""
    from PyPDF2 import PdfReader
    reader = PdfReader(io.BytesIO(content))
    text = ""
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text += t + "\n"
    return text.strip()


def _extract_text_from_docx(content: bytes) -> str:
    """从 Word 文档中提取文本"""
    from docx import Document
    doc = Document(io.BytesIO(content))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return text.strip()


def _extract_text_from_txt(content: bytes) -> str:
    """从纯文本文件中提取"""
    return content.decode("utf-8", errors="replace").strip()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传 Word/PDF/文本文件，提取文字返回"""
    filename = (file.filename or "").lower()
    content = await file.read()

    if not content:
        raise HTTPException(400, "文件为空")

    try:
        if filename.endswith(".pdf"):
            text = _extract_text_from_pdf(content)
        elif filename.endswith(".docx"):
            text = _extract_text_from_docx(content)
        elif filename.endswith((".txt", ".md", ".csv")):
            text = _extract_text_from_txt(content)
        else:
            raise HTTPException(400, f"不支持的文件格式: {file.filename}。支持 PDF、Word、TXT、MD")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"文件解析失败: {str(e)}")

    if not text:
        raise HTTPException(400, "未能从文件中提取到文字，文件可能为扫描件或图片")

    if len(text) < 50:
        raise HTTPException(400, f"提取的文字不足 50 字（实际 {len(text)} 字），请提交更长内容的文件")

    return {
        "filename": file.filename,
        "text": text[:MAX_TEXT_LENGTH],
        "length": len(text),
        "truncated": len(text) > MAX_TEXT_LENGTH,
    }


@router.post("", status_code=201)
async def create_fact_check(req: FactCheckRequest, background_tasks: BackgroundTasks):
    """提交文本进行事实核查，返回 debate_id 用于轮询 /live"""
    text = req.text[:MAX_TEXT_LENGTH]
    debate_id = uuid.uuid4().hex[:12]
    agents_json = json.dumps([
        {"name": "事实核查员", "role": "事实核查", "stance": "事实准确性"},
        {"name": "逻辑分析员", "role": "逻辑分析", "stance": "逻辑严谨性"},
        {"name": "时间线审查员", "role": "时间线审查", "stance": "时间一致性"},
        {"name": "数据验证员", "role": "数据验证", "stance": "数据真实性"},
        {"name": "AI检测员", "role": "AI检测", "stance": "AI痕迹"},
        {"name": "综合审查员", "role": "综合审查", "stance": "综合可信度"},
    ], ensure_ascii=False)

    async with async_session() as db:
        debate = Debate(
            id=debate_id,
            topic=f"文本核查: {text[:40]}...",
            rounds=3,
            status="pending",
            mode="fact_check",
            agents_json=agents_json,
        )
        db.add(debate)
        await db.commit()

    background_tasks.add_task(run_fact_check, text, debate_id)
    return {"debate_id": debate_id, "status": "pending"}
