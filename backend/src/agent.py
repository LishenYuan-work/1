"""辩论 Agent 数据模型"""

from dataclasses import dataclass, field


@dataclass
class DebateAgent:
    """一个辩论 Agent 的定义"""
    name: str           # 显示名称，如 "经济学家"
    role: str           # 角色描述（用作 System Prompt），如 "你是一位自由市场经济学家…"
    stance: str = ""    # 立场倾向，如 "支持", "反对", "中立分析"
    model: str = "deepseek-chat"

    def to_system_prompt(self, topic: str, round_num: int, total_rounds: int) -> str:
        """根据当前轮次生成 System Prompt"""
        round_label = _get_round_label(round_num, total_rounds)
        return (
            f"{self.role}\n\n"
            f"## 辩论话题\n{topic}\n\n"
            f"## 你的立场\n{self.stance}\n\n"
            f"## 当前阶段\n这是第 {round_num}/{total_rounds} 轮：{round_label}\n\n"
            f"## 规则\n"
            f"- 始终保持角色身份，用该角色的专业视角发表观点\n"
            f"- 引用之前其他辩手的发言时，明确指出对方名字和观点再反驳\n"
            f"- 用中文发言，逻辑清晰，有理有据\n"
            f"- 每轮发言控制在 300 字以内"
        )


def _get_round_label(round_num: int, total_rounds: int) -> str:
    """返回当前轮次的标签"""
    if round_num == 1:
        return "开场陈述 — 阐述你的核心观点和论据"
    elif round_num == total_rounds:
        return "总结陈词 — 总结全场辩论，重申你的最终立场"
    else:
        return f"自由辩论 — 针对其他辩手的观点进行反驳和补充"


@dataclass
class DebateMessage:
    """辩论中的一条发言记录"""
    agent_name: str
    content: str
    round_num: int

    def to_chat_message(self) -> dict:
        """转为 OpenAI 消息格式"""
        return {"role": "user", "content": f"[{self.agent_name}]: {self.content}"}


@dataclass
class DebateRecord:
    """一场完整辩论的记录"""
    topic: str
    rounds: int
    agents: list[DebateAgent] = field(default_factory=list)
    messages: list[DebateMessage] = field(default_factory=list)

    def add_message(self, msg: DebateMessage):
        self.messages.append(msg)

    def get_history_for_round(self, round_num: int) -> list[DebateMessage]:
        """获取某轮之前的所有发言历史"""
        return [m for m in self.messages if m.round_num < round_num]

    def to_dict(self) -> dict:
        """转为可序列化的字典"""
        return {
            "topic": self.topic,
            "rounds": self.rounds,
            "agents": [
                {"name": a.name, "role": a.role, "stance": a.stance}
                for a in self.agents
            ],
            "messages": [
                {"agent": m.agent_name, "content": m.content, "round": m.round_num}
                for m in self.messages
            ],
        }
