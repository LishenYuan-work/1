"""辩论编排器 — 多 Agent 辩论的核心调度引擎"""

from typing import Callable, Generator

from src.agent import DebateAgent, DebateMessage, DebateRecord
from src.llm_client import chat, chat_stream
from src.prompts import ROUND_OPENING, ROUND_REBUTTAL, ROUND_CLOSING


# 流式回调类型： (agent_name, round_num, chunk_text) -> None
StreamCallback = Callable[[str, int, str], None]


class DebateOrchestrator:
    """辩论编排器 — 管理多轮多 Agent 辩论流程"""

    def __init__(self, topic: str, agents: list[DebateAgent], total_rounds: int = 3):
        if total_rounds < 2:
            raise ValueError("辩论至少需要 2 轮（开场 + 总结）")
        if len(agents) < 2:
            raise ValueError("至少需要 2 个辩论 Agent")

        self.topic = topic
        self.agents = agents
        self.total_rounds = total_rounds
        self.record = DebateRecord(topic=topic, rounds=total_rounds, agents=agents)

    # ================================================================
    # 同步模式 — 返回完整 DebateRecord
    # ================================================================

    def run(self) -> DebateRecord:
        """同步运行完整辩论，返回辩论记录"""
        for round_num in range(1, self.total_rounds + 1):
            self._run_round(round_num, stream=False)
        return self.record

    # ================================================================
    # 流式模式 — Generator，逐块 yield
    # ================================================================

    def run_stream(self) -> Generator[dict, None, None]:
        """流式运行辩论，每收到一个 token 就 yield 一个事件

        yield 的事件格式:
            {"type": "round_start", "round": 1, "total": 3}
            {"type": "agent_start", "agent": "经济学家", "round": 1}
            {"type": "chunk", "agent": "经济学家", "round": 1, "text": "我认"}
            {"type": "agent_end", "agent": "经济学家", "round": 1, "full_text": "我认为..."}
            {"type": "round_end", "round": 1}
            {"type": "done", "record": DebateRecord}
        """
        for round_num in range(1, self.total_rounds + 1):
            yield {"type": "round_start", "round": round_num, "total": self.total_rounds}

            for agent in self.agents:
                yield {"type": "agent_start", "agent": agent.name, "round": round_num}

                full_text = ""
                for chunk in self._call_agent_stream(agent, round_num):
                    full_text += chunk
                    yield {"type": "chunk", "agent": agent.name, "round": round_num, "text": chunk}

                # 记录发言
                msg = DebateMessage(agent_name=agent.name, content=full_text, round_num=round_num)
                self.record.add_message(msg)

                yield {"type": "agent_end", "agent": agent.name, "round": round_num, "full_text": full_text}

            yield {"type": "round_end", "round": round_num}

        yield {"type": "done", "record": self.record}

    # ================================================================
    # 内部方法
    # ================================================================

    def _run_round(self, round_num: int, stream: bool = False):
        """执行一轮辩论：每个 Agent 依次发言"""
        for agent in self.agents:
            # 构建消息
            messages = self._build_messages(agent, round_num)

            # 调用 LLM
            response = chat(messages=messages)

            # 记录发言
            msg = DebateMessage(agent_name=agent.name, content=response, round_num=round_num)
            self.record.add_message(msg)

    def _call_agent_stream(self, agent: DebateAgent, round_num: int) -> Generator[str, None, None]:
        """流式调用单个 Agent，逐 token yield"""
        messages = self._build_messages(agent, round_num)
        yield from chat_stream(messages=messages)

    def _build_messages(self, agent: DebateAgent, round_num: int) -> list[dict]:
        """为 Agent 构建完整的 messages 列表"""
        messages = []

        # System Prompt：角色定义 + 话题 + 立场 + 当前阶段
        system_prompt = agent.to_system_prompt(self.topic, round_num, self.total_rounds)
        messages.append({"role": "system", "content": system_prompt})

        # 历史发言（之前轮次的所有发言）
        history = self.record.get_history_for_round(round_num)
        for h in history:
            messages.append(h.to_chat_message())

        # 当前轮次的 User Prompt（指导本轮发言风格）
        user_prompt = self._build_user_prompt(agent, round_num)
        messages.append({"role": "user", "content": user_prompt})

        return messages

    def _build_user_prompt(self, agent: DebateAgent, round_num: int) -> str:
        """构建当前轮次的 User Prompt"""
        if round_num == 1:
            return ROUND_OPENING.format(
                round_num=round_num,
                total_rounds=self.total_rounds,
                agent_name=agent.name,
                topic=self.topic,
                stance=agent.stance,
            )

        elif round_num == self.total_rounds:
            # 总结轮：需要包含所有历史
            history_text = self._format_history(round_num)
            return ROUND_CLOSING.format(
                round_num=round_num,
                total_rounds=self.total_rounds,
                agent_name=agent.name,
                debate_history=history_text,
            )

        else:
            # 自由辩论轮
            history_text = self._format_history(round_num)
            return ROUND_REBUTTAL.format(
                round_num=round_num,
                total_rounds=self.total_rounds,
                agent_name=agent.name,
                debate_history=history_text,
                stance=agent.stance,
            )

    def _format_history(self, up_to_round: int) -> str:
        """格式化历史发言为文本"""
        history_msgs = self.record.get_history_for_round(up_to_round)
        if not history_msgs:
            return "（尚无其他发言）"

        lines = []
        for m in history_msgs:
            lines.append(f"[{m.agent_name}] (第{m.round_num}轮): {m.content}")
        return "\n\n".join(lines)
