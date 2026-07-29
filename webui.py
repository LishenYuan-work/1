"""多Agent辩论室"""

import json, os, uuid
from datetime import datetime
import streamlit as st

from src.agent import DebateAgent
from src.roles import get_preset, get_preset_names, recommend_roles
from src.orchestrator import DebateOrchestrator
from src.llm_client import chat
from src.config import config

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debate_history.json")

def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_history(e):
    h = load_history(); h.insert(0, e)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(h, f, ensure_ascii=False, indent=2)

def del_history(eid):
    h = [x for x in load_history() if x.get("id") != eid]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(h, f, ensure_ascii=False, indent=2)

st.set_page_config(page_title="多Agent辩论室", page_icon="🎤", layout="wide", initial_sidebar_state="collapsed")

# 主题色方案
THEMES = {
    "靛蓝（默认）": {"accent":"#4f6ef7","bg":"#f8f9fb","card":"#ffffff","text":"#1a1a2e","sub":"#9098a8","border":"#e8ecf0","input":"#f5f6f8"},
    "琥珀暖橙":     {"accent":"#f08c2e","bg":"#fefaf6","card":"#ffffff","text":"#3d2000","sub":"#a08060","border":"#f0e0d0","input":"#fef6ee"},
    "翡翠绿":       {"accent":"#10b981","bg":"#f5faf7","card":"#ffffff","text":"#0a2818","sub":"#709880","border":"#d8f0e0","input":"#f2faf5"},
    "玫瑰粉":       {"accent":"#ec4899","bg":"#fdf7fa","card":"#ffffff","text":"#2d1020","sub":"#a07088","border":"#f8e0ee","input":"#fdf5f8"},
    "深紫":         {"accent":"#8b5cf6","bg":"#f9f7fd","card":"#ffffff","text":"#1a1030","sub":"#9088a8","border":"#e8e0f8","input":"#f7f4fc"},
    "暗夜模式":     {"accent":"#818cf8","bg":"#1a1b23","card":"#25262f","text":"#d8d8e8","sub":"#8888a0","border":"#353640","input":"#2a2b36"},
}
if "theme" not in st.session_state: st.session_state.theme = "靛蓝（默认）"
COLORS = THEMES[st.session_state.theme]

AGENT_COLORS = [
    ("#6366f1", "🎓"), ("#f59e0b", "⚖️"), ("#10b981", "🔬"),
    ("#ec4899", "💡"), ("#8b5cf6", "🌍"), ("#06b6d4", "🔍"),
]

st.markdown(f"""
<style>
    * {{ font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif; }}
    .stApp {{ background: {COLORS['bg']}; }}
    section[data-testid="stSidebar"] {{ background: {COLORS['card']}; }}
    section[data-testid="stSidebar"] * {{ color: {COLORS['text']} !important; }}
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div {{
        background: {COLORS['input']}; color: {COLORS['text']}; border: 1px solid {COLORS['border']}; border-radius: 8px;
    }}
    .stButton>button[kind="primary"] {{ background: {COLORS['accent']}; border-radius: 8px; border: none; font-weight: 600; }}
    .stButton>button[kind="secondary"] {{ border: 1px solid {COLORS['border']}; border-radius: 8px; }}
    .stProgress>div>div>div {{ background: {COLORS['accent']}; }}

    .msg-box {{
        display: flex; gap: 0.8rem; padding: 0.8rem 0; border-bottom: 1px solid {COLORS['border']};
    }}
    .msg-avatar {{
        width: 42px; height: 42px; border-radius: 10px; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
        color: #fff; font-size: 1rem;
    }}
    .msg-body {{ flex: 1; }}
    .msg-meta {{ display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.3rem; }}
    .msg-name {{ font-weight: 700; font-size: 0.85rem; }}
    .msg-round {{ font-size: 0.65rem; color: {COLORS['sub']}; background: {COLORS['input']}; padding: 2px 8px; border-radius: 10px; }}
    .msg-text {{ line-height: 1.8; font-size: 0.87rem; color: {COLORS['text']}; }}

    .round-divider {{
        text-align: center; padding: 1rem 0; font-size: 0.72rem; font-weight: 700;
        color: {COLORS['accent']}; letter-spacing: 2px;
    }}

    .role-tag {{
        display: inline-block; padding: 0.3rem 0.8rem; margin: 0.1rem;
        border-radius: 6px; font-size: 0.78rem; font-weight: 600;
    }}

    .ask-block {{
        margin: 0.5rem 0 0.5rem 3rem; padding: 0.6rem 0.9rem;
        border-left: 3px solid {COLORS['accent']}; background: {COLORS['input']};
        border-radius: 0 8px 8px 0;
    }}

    .hist-entry {{
        padding: 0.5rem 0.6rem; border-radius: 6px; cursor: pointer;
        border: 1px solid {COLORS['border']}; margin: 0.2rem 0; font-size: 0.8rem;
    }}
</style>
""", unsafe_allow_html=True)

# ========== 侧边栏 ==========
with st.sidebar:
    st.markdown("### 🎨 主题颜色")
    new_theme = st.selectbox("th", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.theme), label_visibility="collapsed")
    if new_theme != st.session_state.theme:
        st.session_state.theme = new_theme; st.rerun()
    st.divider()
    st.markdown("### ⚙️ 设置")
    ak = st.text_input("API 密钥", value=config.api_key or "", type="password", placeholder="sk-...")
    if ak: config.api_key = ak
    with st.expander("🔧 高级"):
        st.slider("随机程度", 0.0, 1.5, config.default_temperature, 0.1, key="tt")
        st.slider("最大字数", 256, 4096, config.default_max_tokens, 128, key="mt")

# ========== 标题 ==========
st.markdown(f'<h1 style="font-size:1.5rem;font-weight:800;color:{COLORS["text"]};margin-bottom:0.2rem;">🎤 多Agent辩论室</h1>', unsafe_allow_html=True)
st.markdown(f'<p style="color:{COLORS["sub"]};font-size:0.85rem;margin-bottom:1rem;">多个 AI Agent 扮演不同角色，围绕话题展开深度辩论</p>', unsafe_allow_html=True)

# ========== 主布局 ==========
left, right = st.columns([1.1, 2.5], gap="medium")

with left:
    # --- 设置卡片 ---
    with st.container(border=True):
        st.markdown("##### 🎯 辩论话题")
        topic = st.text_input("t", placeholder="输入你想辩论的话题…", label_visibility="collapsed")

        st.markdown("##### 🔄 辩论轮次")
        rounds = st.selectbox("r", [2, 3, 4, 5], index=1, format_func=lambda x: f"{x} 轮辩论", label_visibility="collapsed")

        st.markdown("##### 👥 角色来源")
        role_mode = st.radio("m", ["🎯 预设模板", "🤖 AI 推荐", "✏️ 自定义"], label_visibility="collapsed")
        agents = []; role_err = None

        if role_mode == "🎯 预设模板":
            pc = st.selectbox("p", get_preset_names(), label_visibility="collapsed")
            agents = get_preset(pc)
        elif role_mode == "🤖 AI 推荐":
            if st.button("🤖 AI 智能推荐角色", type="secondary", disabled=not topic, use_container_width=True):
                with st.spinner("分析中…"):
                    try: agents = recommend_roles(topic); st.session_state.rec = agents
                    except Exception as e: role_err = str(e)
            agents = st.session_state.get("rec", [])
        else:
            ct = st.text_area("c", placeholder="经济学家\n环保主义者\n企业家", height=70, label_visibility="collapsed")
            if ct.strip():
                agents = [DebateAgent(name=n.strip(), role=f"你是 {n.strip()}，请从专业角度参与辩论。", stance=f"{n.strip()}的视角") for n in ct.split("\n") if n.strip()]

        if agents:
            tags = ""
            for i, a in enumerate(agents):
                cl, em = AGENT_COLORS[i % 6]
                tags += f'<span class="role-tag" style="color:{cl};background:{cl}15;">{em} {a.name}</span>'
            st.markdown(tags, unsafe_allow_html=True)
        if role_err: st.error(role_err)

        ok = bool(topic) and len(agents) >= 2 and bool(ak)
        if not ok:
            for m, c in [("📝 请输入辩论话题", not topic), ("👥 至少需要 2 个角色", len(agents) < 2), ("🔑 请填写 API 密钥", not ak)]:
                if c: st.warning(m)
        go = st.button("🚀 开始辩论", type="primary", disabled=not ok, use_container_width=True)

    # --- 搜索历史 ---
    with st.container(border=True):
        st.markdown("##### 🔍 搜索历史")
        sq = st.text_input("s", placeholder="输入关键词…", label_visibility="collapsed")
        if sq:
            results = [h for h in load_history() if sq.lower() in h.get("topic", "").lower() or any(sq.lower() in m.get("content", "").lower() for m in h.get("messages", []))]
            if results:
                for r in results[:8]:
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.markdown(f'<div class="hist-entry"><span style="font-size:0.65rem;color:{COLORS["sub"]};">{r.get("created_at","")[:16].replace("T"," ")}</span><br><span style="font-weight:600;">{r["topic"][:28]}</span></div>', unsafe_allow_html=True)
                    with c2:
                        if st.button("📖", key=f"v_{r['id'][:8]}"): st.session_state.view_hist = r; st.rerun()
            else:
                st.caption("无匹配记录")

with right:
    # --- 查看历史 ---
    if st.session_state.get("view_hist"):
        h = st.session_state.view_hist
        total = h.get("rounds", 0); cr = 0
        stages = ["开场陈述", "自由辩论", "总结陈词"]
        amap = {a["name"]: i for i, a in enumerate(h.get("agents", []))}

        st.markdown(f'<div style="background:{COLORS["input"]};padding:0.8rem 1rem;border-radius:10px;margin-bottom:1rem;border-left:4px solid {COLORS["accent"]};"><span style="color:{COLORS["sub"]};font-size:0.7rem;">📜 历史记录 · {h.get("created_at","")[:16].replace("T"," ")}</span><br><span style="font-weight:700;color:{COLORS["text"]};">{h["topic"]}</span></div>', unsafe_allow_html=True)

        for m in h.get("messages", []):
            rnd = m.get("round", 1)
            if rnd != cr:
                cr = rnd
                lb = stages[0] if rnd == 1 else (stages[2] if rnd == total else stages[1])
                st.markdown(f'<div class="round-divider">━━ 第 {rnd}/{total} 轮 · {lb} ━━</div>', unsafe_allow_html=True)
            idx = amap.get(m["agent"], 0)
            cl, em = AGENT_COLORS[idx % 6]
            st.markdown(f"""
            <div class="msg-box">
                <div class="msg-avatar" style="background:{cl};">{em}</div>
                <div class="msg-body">
                    <div class="msg-meta">
                        <span class="msg-name" style="color:{cl};">{m["agent"]}</span>
                        <span class="msg-round">第{rnd}轮</span>
                    </div>
                    <div class="msg-text">{m["content"]}</div>
                </div>
            </div>""", unsafe_allow_html=True)

        if st.button("关闭历史记录"):
            st.session_state.view_hist = None
            st.rerun()

    # --- 进行中辩论：执行辩论 ---
    if go and ok:
        # 清除旧记录，开始新辩论
        st.session_state.debate_rec = None
        st.session_state.debate_done = False
        st.session_state.cur_topic = topic; st.session_state.cur_msgs = []; st.session_state.ask = None
        orch = DebateOrchestrator(topic=topic, agents=agents, total_rounds=rounds)

        st.markdown(f'<div style="background:{COLORS["input"]};padding:0.8rem 1rem;border-radius:10px;margin-bottom:1rem;border-left:4px solid {COLORS["accent"]};"><span style="color:{COLORS["sub"]};font-size:0.7rem;">辩论话题</span><br><span style="font-weight:700;color:{COLORS["text"]};">{topic}</span></div>', unsafe_allow_html=True)

        conts, txts = {}, {}
        rph = st.empty(); pph = st.empty()
        total_steps = rounds * len(agents); cs = 0

        for ev in orch.run_stream():
            et = ev["type"]
            if et == "round_start":
                r, tt = ev["round"], ev["total"]
                lb = ["开场陈述", "自由辩论", "总结陈词"][0 if r == 1 else (2 if r == tt else 1)]
                rph.markdown(f'<div class="round-divider">━━ 第 {r}/{tt} 轮 · {lb} ━━</div>', unsafe_allow_html=True)
            elif et == "agent_start":
                nm = ev["agent"]; idx = next((i for i, a in enumerate(agents) if a.name == nm), 0)
                txts[nm] = ""
                if nm not in conts: conts[nm] = st.empty()
            elif et == "chunk":
                nm = ev["agent"]; idx = next((i for i, a in enumerate(agents) if a.name == nm), 0)
                txts[nm] += ev["text"]
                cl, em = AGENT_COLORS[idx % 6]
                conts[nm].markdown(f"""<div class="msg-box"><div class="msg-avatar" style="background:{cl};">{em}</div>
                <div class="msg-body"><div class="msg-meta"><span class="msg-name" style="color:{cl};">{nm}</span>
                <span class="msg-round">第{ev['round']}轮</span></div>
                <div class="msg-text">{txts[nm]}</div></div></div>""", unsafe_allow_html=True)
            elif et == "agent_end":
                nm = ev["agent"]; idx = next((i for i, a in enumerate(agents) if a.name == nm), 0)
                cl, em = AGENT_COLORS[idx % 6]
                conts[nm].markdown(f"""<div class="msg-box"><div class="msg-avatar" style="background:{cl};">{em}</div>
                <div class="msg-body"><div class="msg-meta"><span class="msg-name" style="color:{cl};">{nm}</span>
                <span class="msg-round">第{ev['round']}轮</span></div>
                <div class="msg-text">{ev['full_text']}</div></div></div>""", unsafe_allow_html=True)
                cs += 1; pph.progress(cs / total_steps, text=f"{cs}/{total_steps}")
            elif et == "done":
                rec = ev["record"]
                st.session_state.debate_rec = rec; st.session_state.debate_done = True
                st.session_state.cur_msgs = rec.messages; st.session_state.cur_agents = agents
                save_history({
                    "id": uuid.uuid4().hex[:12], "topic": rec.topic, "rounds": rec.rounds,
                    "created_at": datetime.now().isoformat(),
                    "agents": [{"name": a.name, "role": a.role, "stance": a.stance} for a in rec.agents],
                    "messages": [{"agent": m.agent_name, "content": m.content, "round": m.round_num} for m in rec.messages],
                })

        pph.empty(); rph.empty()
        st.success(f"✅ 辩论完成！{rounds} 轮 · {len(agents)} 位辩手 · {len(orch.record.messages)} 条发言 · 已自动保存")

        # 追问
        st.markdown(f'<p style="font-weight:700;color:{COLORS["text"]};margin-top:1rem;">💬 追问辩手</p>', unsafe_allow_html=True)
        st.caption("对任意发言点击追问按钮，向该辩手单独提问")

        alist = orch.record.agents
        for mi, msg in enumerate(orch.record.messages):
            nm = msg.agent_name; idx = next((i for i, a in enumerate(alist) if a.name == nm), 0)
            ag = alist[idx] if idx < len(alist) else None
            cl, em = AGENT_COLORS[idx % 6]

            c1, c2 = st.columns([15, 1])
            with c1: st.caption(f"{em} {nm} · 第{msg.round_num}轮：{msg.content[:45]}…")
            with c2:
                if st.button("💬", key=f"ak_{mi}", help=f"追问{nm}"):
                    st.session_state.ask = {"name": nm, "role": ag.role if ag else f"你是{nm}", "ctx": msg.content, "mi": mi}
                    st.rerun()

            if st.session_state.get("ask") and st.session_state.ask["mi"] == mi:
                tgt = st.session_state.ask
                fq = st.text_input("追问内容", placeholder=f"问 {tgt['name']}…", key=f"fq_{mi}", label_visibility="collapsed")
                b1, b2 = st.columns([1, 4])
                with b1:
                    if st.button("发送", key=f"fs_{mi}", use_container_width=True) and fq:
                        with st.spinner(f"{tgt['name']} 思考中…"):
                            reply = chat(messages=[{"role": "system", "content": tgt["role"]}, {"role": "user", "content": f"你之前说过：「{tgt['ctx']}」\n\n追问：{fq}\n\n请以你的角色身份回答。"}])
                        st.session_state.ask["reply"] = reply; st.session_state.ask["q"] = fq
                    if st.button("取消", key=f"fc_{mi}"): st.session_state.ask = None; st.rerun()
                if tgt.get("reply"):
                    st.markdown(f'<div class="ask-block"><div style="font-size:0.75rem;color:{COLORS["accent"]};font-weight:700;">💬 {tgt.get("q","")}</div><div style="font-size:0.82rem;color:{COLORS["text"]};margin-top:0.3rem;line-height:1.7;"><strong>{tgt["name"]}：</strong>{tgt["reply"]}</div></div>', unsafe_allow_html=True)
                    if st.button("✓ 完成", key=f"fd_{mi}"): st.session_state.ask = None; st.rerun()

    # --- 辩论结果持久化（追问等操作后保持显示）---
    elif st.session_state.get("debate_done") and st.session_state.get("debate_rec"):
        rec = st.session_state.debate_rec
        agents_rec = st.session_state.get("cur_agents", [])
        st.markdown(f'<div style="background:{COLORS["input"]};padding:0.8rem 1rem;border-radius:10px;margin-bottom:1rem;border-left:4px solid {COLORS["accent"]};"><span style="color:{COLORS["sub"]};font-size:0.7rem;">辩论话题</span><br><span style="font-weight:700;color:{COLORS["text"]};">{rec.topic}</span></div>', unsafe_allow_html=True)

        for mi, msg in enumerate(rec.messages):
            rnd = msg.round_num
            if mi == 0 or rnd != rec.messages[mi-1].round_num:
                lb = ["开场陈述", "自由辩论", "总结陈词"][0 if rnd == 1 else (2 if rnd == rec.rounds else 1)]
                st.markdown(f'<div class="round-divider">━━ 第 {rnd}/{rec.rounds} 轮 · {lb} ━━</div>', unsafe_allow_html=True)
            idx = next((i for i, a in enumerate(agents_rec) if a.name == msg.agent_name), 0)
            cl, em = AGENT_COLORS[idx % 6]
            st.markdown(f"""<div class="msg-box"><div class="msg-avatar" style="background:{cl};">{em}</div>
            <div class="msg-body"><div class="msg-meta"><span class="msg-name" style="color:{cl};">{msg.agent_name}</span>
            <span class="msg-round">第{rnd}轮</span></div>
            <div class="msg-text">{msg.content}</div></div></div>""", unsafe_allow_html=True)

        st.success(f"✅ 辩论完成！{rec.rounds} 轮 · {len(agents_rec)} 位辩手 · {len(rec.messages)} 条发言 · 已自动保存")

        # 追问
        st.markdown(f'<p style="font-weight:700;color:{COLORS["text"]};margin-top:1rem;">💬 追问辩手</p>', unsafe_allow_html=True)
        st.caption("对任意发言点击追问按钮，向该辩手单独提问")

        for mi, msg in enumerate(rec.messages):
            nm = msg.agent_name
            idx = next((i for i, a in enumerate(agents_rec) if a.name == nm), 0)
            ag = agents_rec[idx] if idx < len(agents_rec) else None
            cl, em = AGENT_COLORS[idx % 6]

            c1, c2 = st.columns([15, 1])
            with c1: st.caption(f"{em} {nm} · 第{msg.round_num}轮：{msg.content[:45]}…")
            with c2:
                if st.button("💬", key=f"pk_{mi}", help=f"追问{nm}"):
                    st.session_state.ask = {"name": nm, "role": ag.role if ag else f"你是{nm}", "ctx": msg.content, "mi": mi}
                    st.rerun()

            if st.session_state.get("ask") and st.session_state.ask["mi"] == mi:
                tgt = st.session_state.ask
                fq = st.text_input("追问内容", placeholder=f"问 {tgt['name']}…", key=f"pfq_{mi}", label_visibility="collapsed")
                b1, b2 = st.columns([1, 4])
                with b1:
                    if st.button("发送", key=f"pfs_{mi}", use_container_width=True) and fq:
                        with st.spinner(f"{tgt['name']} 思考中…"):
                            reply = chat(messages=[{"role": "system", "content": tgt["role"]}, {"role": "user", "content": f"你之前说过：「{tgt['ctx']}」\n\n追问：{fq}\n\n请以你的角色身份回答。"}])
                        st.session_state.ask["reply"] = reply; st.session_state.ask["q"] = fq
                    if st.button("取消", key=f"pfc_{mi}"): st.session_state.ask = None; st.rerun()
                if tgt.get("reply"):
                    st.markdown(f'<div class="ask-block"><div style="font-size:0.75rem;color:{COLORS["accent"]};font-weight:700;">💬 {tgt.get("q","")}</div><div style="font-size:0.82rem;color:{COLORS["text"]};margin-top:0.3rem;line-height:1.7;"><strong>{tgt["name"]}：</strong>{tgt["reply"]}</div></div>', unsafe_allow_html=True)
                    if st.button("✓ 完成", key=f"pfd_{mi}"): st.session_state.ask = None; st.rerun()

    # --- 最近历史 ---
    elif not go:
        history_all = load_history()
        if history_all:
            st.markdown(f'<p style="font-weight:700;color:{COLORS["text"]};margin-bottom:0.5rem;">📋 最近辩论</p>', unsafe_allow_html=True)
            for h in history_all[:8]:
                c1, c2, c3 = st.columns([7, 1, 1])
                with c1:
                    st.markdown(f'<div class="hist-entry"><span style="font-size:0.65rem;color:{COLORS["sub"]};">{h.get("created_at","")[:16].replace("T"," ")}</span><br><span style="font-weight:600;">{h["topic"][:35]}</span> <span style="font-size:0.7rem;color:{COLORS["sub"]};">{len(h.get("messages",[]))}条发言</span></div>', unsafe_allow_html=True)
                with c2:
                    if st.button("📖", key=f"rh_{h['id'][:8]}"): st.session_state.view_hist = h; st.rerun()
                with c3:
                    if st.button("🗑", key=f"dh_{h['id'][:8]}"): del_history(h.get("id", "")); st.rerun()
        else:
            st.markdown(f'<div style="text-align:center;padding:4rem 0;color:{COLORS["sub"]};"><div style="font-size:3rem;margin-bottom:0.5rem;opacity:0.4;">🎤</div><div style="font-weight:600;">准备开始辩论</div><div style="font-size:0.85rem;margin-top:0.3rem;">左侧配置参数，点击开始按钮</div></div>', unsafe_allow_html=True)
