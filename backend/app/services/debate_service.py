"""
辩论服务：包装 src/orchestrator.run_stream()

核心职责：
1. 在后台线程中运行同步的 run_stream() 生成器
2. 将每个事件广播到 SSE 管理器
3. 将发言写入数据库
4. 更新辩论状态
"""

import asyncio
import json
import sys
from pathlib import Path

# 确保 src/ 在 import 路径中
_src_path = Path(__file__).resolve().parent.parent.parent / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

from src.agent import DebateAgent, DebateMessage
from src.orchestrator import DebateOrchestrator
from src.llm_client import chat
from app.core.sse_manager import sse_manager
from app.core.config import settings
from app.core.concurrency import debate_limit


async def run_debate_background(debate_id: str, db_session_factory):
    """
    后台执行辩论，通过 SSE 广播事件。

    在 asyncio.to_thread() 中运行同步生成器，
    每 yield 一个事件 → SSE 广播 + 写入 DB。
    完成后更新辩论状态为 completed。
    """
    from app.db.models import Debate, DebateMessage as DebateMessageModel
    from sqlalchemy import select

    # 获取并发槽位
    await debate_limit.acquire(debate_id)

    try:
        async with db_session_factory() as db:
            # 加载辩论记录
            result = await db.execute(select(Debate).where(Debate.id == debate_id))
            debate = result.scalar_one()
            debate.status = "running"
            await db.commit()

            # 从 JSON 重建 Agent 列表
            agents_data = json.loads(debate.agents_json)
            agents = [
                DebateAgent(name=a["name"], role=a["role"], stance=a.get("stance", ""))
                for a in agents_data
            ]

            # 确保 src 配置使用正确的 API 密钥
            import src.config as src_config
            src_config.config.api_key = settings.deepseek_api_key
            src_config.config.model = settings.deepseek_model
            src_config.config.default_temperature = settings.default_temperature
            src_config.config.default_max_tokens = settings.default_max_tokens

            orchestrator = DebateOrchestrator(
                topic=debate.topic,
                agents=agents,
                total_rounds=debate.rounds,
            )

            try:
                # 在后台线程中运行同步生成器
                events = await asyncio.to_thread(lambda: list(orchestrator.run_stream()))

                for event in events:
                    event_type = event["type"]

                    # done 事件中的 DebateRecord 需要转为 dict
                    if event_type == "done" and "record" in event:
                        event = {**event, "record": event["record"].to_dict()}

                    if event_type == "agent_end":
                        # 保存发言到数据库
                        db_msg = DebateMessageModel(
                            debate_id=debate_id,
                            agent_name=event["agent"],
                            round_num=event["round"],
                            content=event["full_text"],
                        )
                        db.add(db_msg)
                        await db.commit()  # 立即写入，让轮询能拉到
                        await asyncio.sleep(3)  # 停顿让观众阅读

                    # 广播到 SSE 管理器
                    await sse_manager.broadcast(debate_id, event_type, event)

                # 标记完成
                debate.status = "completed"
                await db.commit()

            except Exception as e:
                debate.status = "failed"
                debate.error_message = str(e)
                await db.commit()
                await sse_manager.broadcast(debate_id, "error", {"message": str(e)})

        # 发送 done（无论成功失败，关闭 SSE 流）
        await sse_manager.broadcast(debate_id, "done", {
            "debate_id": debate_id,
            "status": debate.status,
        })
    finally:
        debate_limit.release(debate_id)


async def run_followup(agent_config: dict, context_message: str, question: str) -> str:
    """追问某个 Agent：以角色身份回答用户问题"""
    system_prompt = agent_config.get("role", f"你是{agent_config.get('name', '辩手')}")

    user_prompt = (
        f"你之前说过：「{context_message}」\n\n"
        f"有人追问：{question}\n\n"
        f"请以你的角色身份，结合你之前的观点回答这个问题。"
    )

    return await asyncio.to_thread(
        chat,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )


def _run_orchestrator_sync(orchestrator: DebateOrchestrator) -> list[dict]:
    """在同步上下文中运行 orchestrator（供 asyncio.to_thread 调用）"""
    return list(orchestrator.run_stream())
