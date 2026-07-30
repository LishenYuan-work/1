"""事实核查路由"""

import json
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.db.database import async_session
from app.db.models import Debate
from app.services.fact_check_service import run_fact_check

router = APIRouter(prefix="/api/fact-check", tags=["fact-check"])


class FactCheckRequest(BaseModel):
    text: str = Field(..., min_length=50, max_length=5000, description="需要审查的文本")


@router.post("", status_code=201)
async def create_fact_check(req: FactCheckRequest, background_tasks: BackgroundTasks):
    """提交文本进行事实核查，返回 debate_id 用于轮询 /live"""
    debate_id = uuid.uuid4().hex[:12]
    agents_json = json.dumps([
        {"name": "事实核查员", "role": "事实核查", "stance": "事实准确性"},
        {"name": "逻辑分析员", "role": "逻辑分析", "stance": "逻辑严谨性"},
        {"name": "时间线审查员", "role": "时间线审查", "stance": "时间一致性"},
        {"name": "数据验证员", "role": "数据验证", "stance": "数据真实性"},
        {"name": "AI检测员", "role": "AI检测", "stance": "AI痕迹"},
        {"name": "综合审查员", "role": "综合审查", "stance": "综合可信度"},
    ], ensure_ascii=False)

    # 存入数据库（复用 Debate 表）
    async with async_session() as db:
        debate = Debate(
            id=debate_id,
            topic=f"文本核查: {req.text[:40]}...",
            rounds=3,
            status="pending",
            mode="fact_check",
            agents_json=agents_json,
        )
        db.add(debate)
        await db.commit()

    background_tasks.add_task(run_fact_check, req.text, debate_id)
    return {"debate_id": debate_id, "status": "pending"}
