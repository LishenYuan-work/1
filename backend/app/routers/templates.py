"""模板路由：预设模板 + AI 角色推荐"""

import asyncio
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from app.models.schemas import RecommendRequest, RecommendResponse, AgentConfig

# 确保 src/ 在 import 路径中
_src_path = Path(__file__).resolve().parent.parent.parent / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

from src.roles import get_preset, get_preset_names, recommend_roles
from app.core.config import settings

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
async def list_templates():
    """获取所有预设辩论模板"""
    names = get_preset_names()
    templates = []
    for name in names:
        agents = get_preset(name)
        templates.append({
            "name": name,
            "agents": [
                AgentConfig(name=a.name, role=a.role, stance=a.stance)
                for a in agents
            ],
        })
    return templates


@router.get("/{name}")
async def get_template(name: str):
    """获取单个预设模板"""
    try:
        agents = get_preset(name)
        return {
            "name": name,
            "agents": [
                AgentConfig(name=a.name, role=a.role, stance=a.stance)
                for a in agents
            ],
        }
    except ValueError:
        raise HTTPException(404, f"模板 '{name}' 不存在")


@router.post("/ai-recommend", response_model=RecommendResponse)
async def ai_recommend(req: RecommendRequest):
    """AI 智能推荐辩论角色"""
    # 确保配置正确
    import src.config as src_config
    src_config.config.api_key = settings.deepseek_api_key
    src_config.config.model = settings.deepseek_model

    try:
        agents = await asyncio.to_thread(recommend_roles, req.topic)
        return RecommendResponse(
            agents=[AgentConfig(name=a.name, role=a.role, stance=a.stance) for a in agents]
        )
    except Exception as e:
        raise HTTPException(500, f"AI 推荐失败: {str(e)}")
