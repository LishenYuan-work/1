"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { debates, templates } from "@/lib/api";
import type { AgentConfig, Template } from "@/lib/api";
import { Sparkles, Plus, Trash2 } from "lucide-react";

const AGENT_COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#06b6d4"];

export default function CreatePage() {
  const { user } = useAuth();
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [agents, setAgents] = useState<AgentConfig[]>([
    { name: "正方", role: "正方辩手", stance: "支持" },
    { name: "反方", role: "反方辩手", stance: "反对" },
  ]);
  const [rounds, setRounds] = useState(2);
  const [tplList, setTplList] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [recommending, setRecommending] = useState(false);
  const [error, setError] = useState("");

  // 加载预设模板
  useState(() => { templates.list().then(setTplList).catch(() => {}); });

  function applyTemplate(tpl: Template) {
    setAgents(tpl.agents);
  }

  async function aiRecommend() {
    if (!topic.trim()) { setError("请先输入话题"); return; }
    setRecommending(true);
    setError("");
    try {
      const res = await templates.recommend(topic);
      setAgents(res.agents);
    } catch (e) {
      setError(e instanceof Error ? e.message : "推荐失败");
    } finally {
      setRecommending(false);
    }
  }

  function updateAgent(i: number, field: keyof AgentConfig, value: string) {
    setAgents((prev) => prev.map((a, idx) => idx === i ? { ...a, [field]: value } : a));
  }

  function removeAgent(i: number) {
    if (agents.length <= 2) return;
    setAgents((prev) => prev.filter((_, idx) => idx !== i));
  }

  function addAgent() {
    setAgents((prev) => [...prev, { name: `辩手${prev.length + 1}`, role: "", stance: "" }]);
  }

  async function startDebate() {
    if (!user) { setError("请先登录"); return; }
    if (!topic.trim()) { setError("请输入辩论话题"); return; }
    if (agents.length < 2) { setError("至少需要 2 个角色"); return; }
    setLoading(true);
    setError("");
    try {
      const d = await debates.create({ topic: topic.trim(), agents, rounds, visibility: "public" });
      router.push(`/debate?id=${d.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-3xl mx-auto px-1 sm:px-0">
      <h1 className="text-xl font-bold mb-6">创建辩论</h1>

      {/* 话题 */}
      <div className="mb-4">
        <label className="block text-sm font-semibold mb-1">辩论话题</label>
        <input type="text" value={topic} onChange={(e) => setTopic(e.target.value)}
          placeholder="输入你想辩论的话题…"
          className="w-full px-3 py-2 rounded-lg border text-sm"
          style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }} />
      </div>

      {/* 预设模板 */}
      <div className="mb-4">
        <label className="block text-sm font-semibold mb-2">角色来源</label>
        <div className="flex flex-wrap gap-2 mb-2">
          {tplList.map((tpl) => (
            <button key={tpl.name} onClick={() => applyTemplate(tpl)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold border cursor-pointer transition-colors"
              style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }}>
              {tpl.name} ({tpl.agents.length}人)
            </button>
          ))}
          <button onClick={aiRecommend} disabled={recommending}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold border cursor-pointer flex items-center gap-1"
            style={{ borderColor: "var(--accent)", color: "var(--accent)", background: "transparent" }}>
            <Sparkles size={14} /> {recommending ? "分析中…" : "AI 智能推荐"}
          </button>
        </div>
      </div>

      {/* 角色编辑 */}
      <div className="mb-4">
        <label className="block text-sm font-semibold mb-2">辩论角色 ({agents.length})</label>
        <div className="flex flex-col gap-2">
          {agents.map((a, i) => (
            <div key={i} className="flex flex-col sm:flex-row items-start sm:items-center gap-1.5 sm:gap-2 p-2 sm:p-3 rounded-lg border"
              style={{ borderColor: "var(--border)", background: "var(--card)" }}>
              <div className="flex items-center gap-2 w-full sm:w-auto">
                <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                  style={{ background: AGENT_COLORS[i % 6] }}>{i + 1}</div>
                <input type="text" value={a.name} onChange={(e) => updateAgent(i, "name", e.target.value)}
                  placeholder="名称" className="w-16 sm:w-20 px-2 py-1 rounded border text-xs"
                  style={{ borderColor: "var(--border)", background: "var(--bg)", color: "var(--text)" }} />
                <input type="text" value={a.stance} onChange={(e) => updateAgent(i, "stance", e.target.value)}
                  placeholder="立场" className="w-16 sm:w-20 px-2 py-1 rounded border text-xs"
                  style={{ borderColor: "var(--border)", background: "var(--bg)", color: "var(--text)" }} />
                <button onClick={() => removeAgent(i)} className="sm:hidden bg-transparent border-0 cursor-pointer flex-shrink-0"
                  style={{ color: "var(--sub)" }}><Trash2 size={14} /></button>
              </div>
              <div className="flex items-center gap-2 w-full">
                <input type="text" value={a.role} onChange={(e) => updateAgent(i, "role", e.target.value)}
                  placeholder="角色描述" className="flex-1 px-2 py-1 rounded border text-xs w-full"
                  style={{ borderColor: "var(--border)", background: "var(--bg)", color: "var(--text)" }} />
                <button onClick={() => removeAgent(i)}
                  className="hidden sm:block bg-transparent border-0 cursor-pointer flex-shrink-0" style={{ color: "var(--sub)" }}>
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
        <button onClick={addAgent}
          className="mt-2 px-3 py-1 rounded-lg text-xs font-semibold border cursor-pointer flex items-center gap-1"
          style={{ borderColor: "var(--border)", color: "var(--sub)", background: "transparent" }}>
          <Plus size={14} /> 添加角色
        </button>
      </div>

      {/* 轮次 */}
      <div className="mb-6">
        <label className="block text-sm font-semibold mb-1">辩论轮次: {rounds}</label>
        <input type="range" min="2" max="10" value={rounds} onChange={(e) => setRounds(Number(e.target.value))}
          className="w-full" style={{ accentColor: "var(--accent)" }} />
        <div className="flex justify-between text-xs" style={{ color: "var(--sub)" }}>
          <span>2 轮（简短）</span><span>10 轮（深度）</span>
        </div>
      </div>

      {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

      <button onClick={startDebate} disabled={loading}
        className="w-full py-3 rounded-xl text-white font-bold text-base border-0 cursor-pointer disabled:opacity-50"
        style={{ background: loading ? "var(--sub)" : "var(--accent)" }}>
        {loading ? "正在创建…" : "开始辩论"}
      </button>
    </div>
  );
}
