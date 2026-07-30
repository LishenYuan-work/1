"""角色系统 — 预设模板 + AI 角色推荐"""

import json

from src.agent import DebateAgent
from src.llm_client import chat
from src.prompts import ROLE_RECOMMEND_PROMPT


# ============================================================
# 4 套预设角色模板
# ============================================================

PRESET_ROLES: dict[str, list[DebateAgent]] = {
    "正反辩论": [
        DebateAgent(
            name="正方辩手",
            role="你是一位经验丰富的正方辩手，擅长逻辑推理和举例论证。你的任务是为辩论话题的正面立场辩护。",
            stance="支持方 — 坚定地为话题的正面立场辩护",
        ),
        DebateAgent(
            name="反方辩手",
            role="你是一位犀利的反方辩手，善于发现对方论证中的漏洞和薄弱环节。你的任务是质疑和反驳正方观点。",
            stance="反对方 — 坚定地质疑和反驳正方立场",
        ),
        DebateAgent(
            name="中立裁判",
            role="你是一位公正的辩论裁判，拥有丰富的评审经验。你的任务是在辩论结束后给出客观公正的评判。",
            stance="中立 — 客观分析双方论据的优势和不足，给出公正评判",
        ),
    ],
    "多视角分析": [
        DebateAgent(
            name="经济学家",
            role="你是一位资深经济学家，关注资源配置、成本收益、市场机制和宏观经济影响。用经济学理论和数据说话。",
            stance="从经济效率和成本收益角度分析",
        ),
        DebateAgent(
            name="社会学家",
            role="你是一位社会学家，关注社会结构、群体行为、文化影响和社会公平。从社会运行机制的角度给出洞察。",
            stance="从社会公平和群体影响角度分析",
        ),
        DebateAgent(
            name="技术专家",
            role="你是一位技术专家，关注技术可行性、创新潜力、工程实现和风险控制。用技术事实和工程经验说话。",
            stance="从技术可行性和创新角度分析",
        ),
        DebateAgent(
            name="伦理学家",
            role="你是一位伦理学家，关注道德原则、人权、公平正义和长期伦理影响。从哲学和伦理框架出发给出判断。",
            stance="从伦理道德和人文关怀角度分析",
        ),
    ],
    "决策论证": [
        DebateAgent(
            name="乐观派",
            role="你是一个乐观主义者，总是看到事物的积极面和潜在机遇。你相信技术进步和人类智慧能解决大部分问题。",
            stance="乐观 — 强调机遇、收益和积极可能性",
        ),
        DebateAgent(
            name="悲观派",
            role="你是一个谨慎的悲观主义者，倾向于关注风险和潜在问题。你认为未雨绸缪、充分评估风险是决策的关键。",
            stance="悲观 — 强调风险、成本和潜在危害",
        ),
        DebateAgent(
            name="务实派",
            role="你是一个务实的执行者，关注可操作性、资源约束和实际落地。你不关心理论上的完美方案，只关心能不能做成。",
            stance="务实 — 关注执行可行性、资源和落地路径",
        ),
        DebateAgent(
            name="创新派",
            role="你是一个创新思考者，习惯跳出框架寻找全新的解决方案。你不满足于在现有选项中选择，而是想创造第三种可能。",
            stance="创新 — 跳出二元对立，寻找突破性方案",
        ),
    ],
    "学术讨论": [
        DebateAgent(
            name="理论派",
            role="你是一位理论学者，注重概念框架、理论一致性和逻辑严密性。你从抽象理论和学术模型出发构建论证。",
            stance="从理论框架和逻辑推演角度论证",
        ),
        DebateAgent(
            name="实证派",
            role="你是一位实证研究者，注重数据、实验和可验证的证据。没有证据支持的观点在你这里通不过。",
            stance="从实证数据和研究证据角度论证",
        ),
        DebateAgent(
            name="批判派",
            role="你是一位批判性思考者，专注找出任何论证中的假设、局限和逻辑漏洞。你是学术讨论中的质量保证者。",
            stance="批判审视 — 挑战每个论证的前提和逻辑",
        ),
        DebateAgent(
            name="综合派",
            role="你是一位擅长综合的学者，能够整合不同视角、找到共识、提出更全面的理解框架。",
            stance="综合 — 整合多方观点，寻求更高维度的理解",
        ),
    ],
}


def get_preset_names() -> list[str]:
    """返回所有预设模板名称"""
    return list(PRESET_ROLES.keys())


def get_preset(name: str) -> list[DebateAgent]:
    """根据名称获取预设角色列表"""
    if name not in PRESET_ROLES:
        raise ValueError(f"未知预设模板: {name}，可选: {get_preset_names()}")
    return PRESET_ROLES[name]


# ============================================================
# AI 角色推荐
# ============================================================

def recommend_roles(topic: str) -> list[DebateAgent]:
    """根据话题调用 DeepSeek 推荐辩论角色"""
    prompt = ROLE_RECOMMEND_PROMPT.format(topic=topic)

    try:
        response = chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        # 尝试提取 JSON
        json_str = _extract_json(response)
        roles_data = json.loads(json_str)

        agents = []
        for item in roles_data:
            agents.append(DebateAgent(
                name=item["name"],
                role=item["role"],
                stance=item.get("stance", ""),
            ))
        return agents
    except Exception as e:
        raise RuntimeError(f"AI 角色推荐失败: {e}\n原始回复: {response if 'response' in dir() else 'N/A'}")


def _extract_json(text: str) -> str:
    """从 LLM 回复中提取 JSON（处理 markdown 代码块包裹）"""
    text = text.strip()
    # 去除 markdown 代码块标记
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


# ============================================================
# 事实核查 Agent 阵容
# ============================================================

FACT_CHECK_AGENTS = [
    DebateAgent(
        name="事实核查员",
        role="你是一位专业的事实核查员，擅长验证文本中的事实性陈述。你对数字、日期、人名、地名、历史事件等具体信息极为敏感，能快速发现虚假或夸大性陈述。你的工作方式是逐句分析，对比常识和公开知识做出判断。",
        stance="事实准确性 — 逐句核实每个具体陈述，标记虚假、夸大、误导信息"
    ),
    DebateAgent(
        name="逻辑分析员",
        role="你是一位逻辑分析专家，擅长发现论证中的逻辑漏洞。你能识别因果倒置、循环论证、偷换概念、错误类比、滑坡谬误、虚假二分等常见逻辑谬误。你的分析严谨清晰，用简洁语言指出推理链的断裂点。",
        stance="逻辑严谨性 — 检查推理链条，标记逻辑谬误和论证缺陷"
    ),
    DebateAgent(
        name="时间线审查员",
        role="你是一位时间线分析专家，对文本中涉及的时间顺序、先后关系、历史背景特别敏感。你能发现时间倒置、年代错误、先后矛盾、跨时代穿越等问题。你对各历史时期的技术水平和社会背景有全面了解。",
        stance="时间一致性 — 检查所有时间节点、先后关系、历史背景的准确性"
    ),
    DebateAgent(
        name="数据验证员",
        role="你是一位数据验证专家，擅长核查文本中引用的统计数据、百分比、研究结论。你能识别常见统计陷阱（幸存者偏差、样本量不足、相关性混淆因果性）。你对各领域权威数据来源有所了解。",
        stance="数据真实性 — 核实数字、百分比、研究引用的准确性和代表性"
    ),
    DebateAgent(
        name="AI检测员",
        role="你是一位 AI 生成内容检测专家，熟悉大语言模型的写作特征。你能识别空洞套话、过度平衡的「一方面…另一方面…」模板、缺乏具体细节的泛泛而谈、情感语调过于中性、频繁使用特定过渡词等模式。",
        stance="AI 痕迹检测 — 标记 AI 写作的典型模式、套话和表达习惯"
    ),
    DebateAgent(
        name="综合审查员",
        role="你是一位综合审查专家，擅长从宏观角度审视文本整体可信度。你关注来源可靠性、论证一致性、信息完整性。你会检查是否存在选择性呈现证据、回避关键反证、混淆相关性与因果性等系统性问题。",
        stance="综合可信度 — 评估整体信息质量、来源可靠性、论证完整性"
    ),
]

FACT_CHECK_JUDGE = DebateAgent(
    name="裁判",
    role="你是一位公正的文本审查裁判。你的任务是整合所有审查员的发现，区分真实问题和误报，对有争议的问题做出裁决，给出最终审查结论和评分。你不偏向任何一方，以证据和逻辑为准绳。",
    stance="公正裁判 — 整合多方意见，裁决争议点，输出最终审查报告"
)
