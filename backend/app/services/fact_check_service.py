"""
事实核查服务 — 多 Agent 文本审查 + 交叉辩论 + 裁判总结

流程：
1. 独立审查：每个 Agent 逐句分析文本
2. 交叉辩论：Agent 查看其他人的发现，辩论分歧
3. 裁判总结：整合所有意见，输出最终报告
"""

import asyncio
import sys
from pathlib import Path

_src_path = Path(__file__).resolve().parent.parent.parent / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

from src.llm_client import chat
from src.prompts import FACT_CHECK_SYSTEM, FACT_CHECK_OPENING, FACT_CHECK_DEBATE, FACT_CHECK_JUDGE
from src.roles import FACT_CHECK_AGENTS, FACT_CHECK_JUDGE
from app.core.sse_manager import sse_manager
from app.core.config import settings
from app.core.web_search import search_factual_claims, format_search_results


def _ensure_api_key():
    import src.config as src_config
    src_config.config.api_key = settings.deepseek_api_key
    src_config.config.model = settings.deepseek_model
    src_config.config.default_temperature = 0.3  # 事实核查用低温度，更严谨
    src_config.config.default_max_tokens = 2048


async def run_fact_check(text: str, debate_id: str, total_rounds: int = 2):
    """异步执行事实核查：可变轮数"""
    _ensure_api_key()

    from app.db.models import Debate, DebateMessage as DebateMessageModel
    from app.db.database import async_session
    from sqlalchemy import select

    agents = FACT_CHECK_AGENTS
    judge = FACT_CHECK_JUDGE

    async def save_msg(agent_name: str, content: str, round_num: int):
        """保存发言到数据库"""
        async with async_session() as db:
            msg = DebateMessageModel(debate_id=debate_id, agent_name=agent_name, content=content, round_num=round_num)
            db.add(msg)
            await db.commit()

    async def update_status(status: str):
        async with async_session() as db:
            r = await db.execute(select(Debate).where(Debate.id == debate_id))
            d = r.scalar_one_or_none()
            if d:
                d.status = status
                await db.commit()

    await update_status("running")

    total_display = total_rounds + 1  # 显示轮数 = 核查轮数 + 裁判总结
    label_names: dict[int, str] = {0: "联网检索"}
    for i in range(1, total_rounds + 1):
        label_names[i] = f"第{i}轮核查" if i <= total_rounds else "裁判总结"
    label_names[total_display] = "裁判总结"

    # ====== RAG：联网搜索 ======
    await sse_manager.broadcast(debate_id, "round_start", {
        "round": 0, "total": total_display, "label": "联网检索 — 搜索相关事实进行交叉验证"
    })
    await sse_manager.broadcast(debate_id, "agent_start", {"agent": "搜索引擎", "round": 0})

    search_results = await asyncio.to_thread(search_factual_claims, text)
    search_text = format_search_results(search_results)

    await sse_manager.broadcast(debate_id, "agent_end", {
        "agent": "搜索引擎", "round": 0,
        "full_text": f"已检索 {len(search_results)} 条相关资料，将作为核查参考依据。"
    })
    await sse_manager.broadcast(debate_id, "round_end", {"round": 0})

    # ====== 第 1 轮：独立审查 ======
    await sse_manager.broadcast(debate_id, "round_start", {
        "round": 1, "total": total_display, "label": "独立审查 — 各 Agent 逐句分析"
    })

    findings: dict[str, str] = {}

    for agent in agents:
        await sse_manager.broadcast(debate_id, "agent_start", {"agent": agent.name, "round": 1})

        # 注入搜索结果
        system = FACT_CHECK_SYSTEM.format(role=agent.role, text=text)
        if search_text:
            system += f"\n\n## 联网搜索结果（供交叉验证）\n以下是从网络搜索到的最新资料，请用于核实文本中的事实陈述：\n\n{search_text}"
        user = FACT_CHECK_OPENING.format(stance=agent.stance)
        response = await asyncio.to_thread(chat, messages=[
            {"role": "system", "content": system}, {"role": "user", "content": user},
        ])

        findings[agent.name] = response
        await save_msg(agent.name, response, 1)
        await sse_manager.broadcast(debate_id, "agent_end", {"agent": agent.name, "round": 1, "full_text": response})
        await asyncio.sleep(1)

    await sse_manager.broadcast(debate_id, "round_end", {"round": 1})

    # ====== 多轮交叉辩论 ======
    debate_findings: dict[str, str] = dict(findings)  # 初始化为第一轮的发现

    for debate_round in range(2, total_rounds + 1):
        await sse_manager.broadcast(debate_id, "round_start", {
            "round": debate_round, "total": total_display,
            "label": f"第{debate_round}轮辩论 — 交叉审查与深度讨论"
        })

        new_findings: dict[str, str] = {}
        for agent in agents:
            others = {k: v for k, v in debate_findings.items() if k != agent.name}
            other_text = "\n\n".join(f"### {k}\n{v}" for k, v in others.items())

            await sse_manager.broadcast(debate_id, "agent_start", {"agent": agent.name, "round": debate_round})

            response = await asyncio.to_thread(chat, messages=[
                {"role": "system", "content": FACT_CHECK_SYSTEM.format(role=agent.role, text=text)},
                {"role": "user", "content": FACT_CHECK_DEBATE.format(other_findings=other_text)},
            ])

            new_findings[agent.name] = response
            debate_findings[agent.name] = response  # 更新最新发现
            await save_msg(agent.name, response, debate_round)
            await sse_manager.broadcast(debate_id, "agent_end", {"agent": agent.name, "round": debate_round, "full_text": response})
            await asyncio.sleep(1)

        await sse_manager.broadcast(debate_id, "round_end", {"round": debate_round})

    # ====== 裁判总结 ======
    await sse_manager.broadcast(debate_id, "round_start", {
        "round": total_display, "total": total_display, "label": "裁判总结 — 整合结论"
    })

    all_text = "\n\n".join(
        f"## {name}\n### 第一轮发现\n{findings[name]}\n### 第二轮辩论\n{debate_findings[name]}"
        for name in [a.name for a in agents]
    )

    await sse_manager.broadcast(debate_id, "agent_start", {"agent": judge.name, "round": total_display})

    verdict = await asyncio.to_thread(chat, messages=[
        {"role": "system", "content": judge.role},
        {"role": "user", "content": FACT_CHECK_JUDGE.format(all_findings=all_text)},
    ])

    await save_msg(judge.name, verdict, total_display)
    await sse_manager.broadcast(debate_id, "agent_end", {"agent": judge.name, "round": total_display, "full_text": verdict})
    await sse_manager.broadcast(debate_id, "round_end", {"round": total_display})

    await update_status("completed")
    await sse_manager.broadcast(debate_id, "done", {"status": "completed"})
