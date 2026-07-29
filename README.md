# 🎤 多Agent辩论式团队

基于 **DeepSeek API** 的多 Agent 协作辩论系统。多个 AI Agent 扮演不同角色，围绕任意话题展开多轮深度辩论。

## ✨ 特性

- 🎭 **多角色辩论** — 支持 2-N 个 Agent，每个 Agent 有独立角色和立场
- 📋 **4套预设模板** — 正反辩论 / 多视角分析 / 决策论证 / 学术讨论，开箱即用
- 🤖 **AI 角色推荐** — 输入话题，AI 自动推荐最适合的辩论角色
- 🔄 **多轮辩论** — 可配置辩论轮次（开场陈述 → 自由辩论 → 总结陈词）
- 🖥️ **双界面** — CLI（终端流式输出）+ Web UI（Streamlit 浏览器界面）
- ⚡ **流式输出** — 实时看到 Agent 逐字生成发言，体验流畅
- 🔌 **DeepSeek API** — 使用 OpenAI 兼容接口，轻松替换为其他模型

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# 复制配置模板
copy .env.example .env    # Windows
cp .env.example .env      # Mac/Linux

# 编辑 .env，填入你的 DeepSeek API Key
# 获取 Key: https://platform.deepseek.com/api_keys
```

### 3. 运行

**CLI 模式（终端）：**

```bash
# 使用预设模板
python cli.py debate "AI是否应该被严格监管" --preset 正反辩论 --rounds 3

# 自定义角色
python cli.py debate "远程办公的利弊" --roles 支持者,反对者,企业管理者 --rounds 2

# AI 自动推荐角色
python cli.py debate "全球变暖应对方案" --ai-roles

# 单独使用 AI 推荐
python cli.py recommend "是否应该全面禁止塑料"
```

**Web UI 模式（浏览器）：**

```bash
streamlit run webui.py
```

然后浏览器打开 `http://localhost:8501`

## 📁 项目结构

```
debate-agents/
├── cli.py                  # CLI 入口（Click + Rich）
├── webui.py                # Streamlit Web UI
├── src/
│   ├── config.py           # 配置管理（环境变量）
│   ├── llm_client.py       # DeepSeek API 封装
│   ├── agent.py            # Agent 数据模型
│   ├── prompts.py          # Prompt 模板
│   ├── roles.py            # 角色系统（预设 + AI推荐）
│   └── orchestrator.py     # 辩论编排器（核心）
├── requirements.txt
├── .env.example
└── README.md
```

## 🏗️ 架构设计

```
用户输入（话题 + 角色 + 轮次）
         │
         ▼
   DebateOrchestrator（编排器）
         │
         ├── Round 1: 开场陈述 ── 每个 Agent 依次发言
         ├── Round 2~N-1: 自由辩论 ── Agent 看到历史后反驳
         └── Round N: 总结陈词 ── 最终立场申明
         │
         ▼
   完整辩论记录（DebateRecord）
```

核心设计要点：
- **顺序发言**：每个 Agent 发言时可看到之前所有人的发言，辩论逻辑合理
- **System Prompt 区分角色**：所有 Agent 共用 DeepSeek Chat 模型，通过不同的 System Prompt 赋予不同人格
- **流式回调**：Orchestrator 通过 Generator 逐 token 输出，CLI 和 Web 复用同一套流式接口
- **无框架依赖**：不引入 LangChain/CrewAI，从零手写编排器，利于理解 Agent 协作原理

## 🔧 预设辩论模板

| 模板名称 | 角色 | 适用场景 |
|---------|------|---------|
| 正反辩论 | 正方辩手 + 反方辩手 + 中立裁判 | 二元对立话题 |
| 多视角分析 | 经济学家 + 社会学家 + 技术专家 + 伦理学家 | 复杂社会议题 |
| 决策论证 | 乐观派 + 悲观派 + 务实派 + 创新派 | 决策评估 |
| 学术讨论 | 理论派 + 实证派 + 批判派 + 综合派 | 学术话题探讨 |

## 📝 示例

```bash
$ python cli.py debate "是否应该全面禁止塑料制品" --preset 多视角分析 --rounds 3

🎤 辩论开始
辩论话题: 是否应该全面禁止塑料制品

👥 辩论角色 (预设模板: 多视角分析)
┌────────────┬──────────────────────────┐
│ 角色       │ 立场                     │
├────────────┼──────────────────────────┤
│ 经济学家   │ 从经济效率和成本收益分析 │
│ 社会学家   │ 从社会公平和群体影响分析 │
│ 技术专家   │ 从技术可行性和创新分析   │
│ 伦理学家   │ 从伦理道德和人文关怀分析 │
└────────────┴──────────────────────────┘

━━━━━━━━━━━━ 第 1/3 轮 ━━━━━━━━━━━━

📣 经济学家: 从经济角度看，全面禁止塑料制品...
📣 社会学家: 塑料污染对低收入社区影响最大...
📣 技术专家: 目前生物降解塑料技术已趋成熟...
📣 伦理学家: 我们有道德责任为后代保护环境...

━━━━━━━━━━━━ 第 2/3 轮 ━━━━━━━━━━━━
...
```

## 🛠️ 技术要求

- Python 3.11+
- DeepSeek API Key（[获取地址](https://platform.deepseek.com/api_keys)）
- 网络连接

## 📄 License

MIT
