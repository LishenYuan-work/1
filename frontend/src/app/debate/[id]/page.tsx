"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { debates, type DebateDetail, type SSEEvent } from "@/lib/api";
import { useDebateStream } from "@/lib/use-sse";
import { Send, Loader2 } from "lucide-react";
import CommentSection from "@/components/CommentSection";

const AGENT_COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#06b6d4"];
const AGENT_EMOJIS = ["🎓", "⚖️", "🔬", "💡", "🌍", "🔍"];

const ROUND_LABELS = (r: number, total: number) =>
  r === 1 ? "开场陈述" : r === total ? "总结陈词" : "自由辩论";

export default function DebatePage() {
  const { id } = useParams<{ id: string }>();
  const [debate, setDebate] = useState<DebateDetail | null>(null);
  const [followQ, setFollowQ] = useState<Record<number, string>>({});
  const [followReply, setFollowReply] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);

  const { events, connected, done } = useDebateStream(id);

  // 加载辩论数据
  useEffect(() => {
    debates.get(id).then((d) => {
      setDebate(d);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  // 将已有消息 + SSE 事件合并展示
  const agentIndexMap = useRef<Record<string, number>>({});

  const existingMessages = debate?.messages || [];
  const agentNames = debate?.agents.map((a) => a.name) || [];

  // 为 SSE 事件中的 agent 分配颜色索引
  for (const ev of events) {
    if ((ev.type === "agent_start" || ev.type === "agent_end") && !(ev.agent in agentIndexMap.current)) {
      agentIndexMap.current[ev.agent] = Object.keys(agentIndexMap.current).length;
    }
  }
  for (const a of agentNames) {
    if (!(a in agentIndexMap.current)) agentIndexMap.current[a] = Object.keys(agentIndexMap.current).length;
  }

  // 构建实时消息列表
  const streamMessages: { agent_name: string; content: string; round_num: number; streaming?: boolean }[] = [];
  const seenRounds = new Set<number>();

  for (const ev of events) {
    if (ev.type === "round_start") seenRounds.add(ev.round);
  }

  // 已有的完整消息
  const lastMsgRound = existingMessages.length > 0 ? existingMessages[existingMessages.length - 1].round_num : 0;

  for (const msg of existingMessages) {
    streamMessages.push(msg);
  }

  // SSE 实时消息
  const activeStreams: Record<string, string> = {};
  let currentRound = lastMsgRound + 1;
  for (const ev of events) {
    if (ev.type === "round_start") currentRound = ev.round;
    if (ev.type === "chunk") {
      activeStreams[ev.agent] = (activeStreams[ev.agent] || "") + ev.text;
    }
  }

  // 把正在流式输入的 agent 追加到消息列表
  for (const [agent, text] of Object.entries(activeStreams)) {
    if (text && !existingMessages.some((m) => m.agent_name === agent && m.round_num === currentRound)) {
      streamMessages.push({ agent_name: agent, content: text, round_num: currentRound, streaming: true });
    }
  }

  async function handleFollowup(msgIdx: number) {
    const q = followQ[msgIdx];
    if (!q?.trim()) return;
    try {
      const res = await debates.followup(id, { message_index: msgIdx, question: q });
      setFollowReply((prev) => ({ ...prev, [msgIdx]: res.reply }));
      setFollowQ((prev) => ({ ...prev, [msgIdx]: "" }));
    } catch (e) {
      setFollowReply((prev) => ({ ...prev, [msgIdx]: "追问失败: " + (e instanceof Error ? e.message : "") }));
    }
  }

  if (loading) {
    return <div className="text-center py-20" style={{ color: "var(--sub)" }}><Loader2 className="animate-spin mx-auto" size={32} />加载中…</div>;
  }

  if (!debate) {
    return <div className="text-center py-20" style={{ color: "var(--sub)" }}>辩论不存在</div>;
  }

  // 确定当前轮次
  const allRounds = new Set<number>();
  for (const m of streamMessages) allRounds.add(m.round_num);
  for (const ev of events) { if (ev.type === "round_start") allRounds.add(ev.round); }
  const rounds = Array.from(allRounds).sort((a, b) => a - b);

  return (
    <div className="w-full max-w-4xl mx-auto px-0 sm:px-1">
      {/* 头部 */}
      <div className="p-3 sm:p-4 rounded-xl mb-4 sm:mb-6" style={{ background: "var(--card)", borderLeft: "4px solid var(--accent)" }}>
        <span className="text-xs" style={{ color: "var(--sub)" }}>辩论话题</span>
        <h1 className="text-lg font-bold m-0 mt-1">{debate.topic}</h1>
        <div className="flex items-center gap-3 mt-2 text-xs" style={{ color: "var(--sub)" }}>
          <span>{debate.agents.length} 位辩手</span>
          <span>·</span>
          <span>{debate.rounds} 轮</span>
          <span>·</span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full"
              style={{ background: connected ? "#10b981" : done ? "var(--accent)" : "var(--sub)" }} />
            {connected ? "直播中" : done ? "已完成" : debate.status}
          </span>
        </div>
      </div>

      {/* 消息流 */}
      <div>
        {rounds.map((r) => (
          <div key={r}>
            <div className="text-center py-4 text-xs font-bold tracking-wider"
              style={{ color: "var(--accent)" }}>
              ━━ 第 {r}/{debate.rounds} 轮 · {ROUND_LABELS(r, debate.rounds)} ━━
            </div>
            {streamMessages
              .filter((m) => m.round_num === r)
              .map((msg, mi) => {
                const idx = agentIndexMap.current[msg.agent_name] || 0;
                const cl = AGENT_COLORS[idx % 6];
                const em = AGENT_EMOJIS[idx % 6];
                const globalIdx = (r - 1) * debate.agents.length + mi;

                return (
                  <div key={`${r}-${mi}`} className="flex gap-2 sm:gap-3 py-2.5 sm:py-3" style={{ borderBottom: "1px solid var(--border)" }}>
                    <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg sm:rounded-xl flex items-center justify-center text-white flex-shrink-0 text-xs sm:text-base"
                      style={{ background: cl }}>{em}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 sm:gap-2 mb-1 flex-wrap">
                        <span className="font-bold text-xs sm:text-sm" style={{ color: cl }}>{msg.agent_name}</span>
                        <span className="text-[10px] sm:text-xs px-1.5 py-0.5 rounded-md"
                          style={{ color: "var(--sub)", background: "var(--bg)" }}>第{r}轮</span>
                        {msg.streaming && <span className="text-[10px] sm:text-xs animate-pulse" style={{ color: "var(--accent)" }}>输入中…</span>}
                      </div>
                      <div className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap break-words">{msg.content}</div>

                      {/* 追问按钮（非流式消息才显示） */}
                      {!msg.streaming && (
                        <div className="mt-2">
                          <button onClick={() => {
                            const newState = { ...followQ };
                            newState[globalIdx] = newState[globalIdx] || "";
                            setFollowQ(newState);
                          }}
                            className="text-xs bg-transparent border-0 cursor-pointer"
                            style={{ color: "var(--sub)" }}>
                            💬 追问
                          </button>
                          {followQ[globalIdx] !== undefined && (
                            <div className="mt-1 flex gap-2">
                              <input type="text" value={followQ[globalIdx]}
                                onChange={(e) => setFollowQ((p) => ({ ...p, [globalIdx]: e.target.value }))}
                                onKeyDown={(e) => e.key === "Enter" && handleFollowup(globalIdx)}
                                placeholder={`问 ${msg.agent_name}…`}
                                className="flex-1 px-2 py-1 rounded border text-xs"
                                style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }} />
                              <button onClick={() => handleFollowup(globalIdx)}
                                className="px-2 py-1 rounded text-white text-xs border-0 cursor-pointer"
                                style={{ background: "var(--accent)" }}>
                                <Send size={12} />
                              </button>
                            </div>
                          )}
                          {followReply[globalIdx] && (
                            <div className="mt-1 p-2 rounded-lg text-xs leading-relaxed"
                              style={{ background: "var(--bg)", borderLeft: "3px solid var(--accent)" }}>
                              <strong>{msg.agent_name}：</strong>{followReply[globalIdx]}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
          </div>
        ))}
      </div>

      {/* 空状态 */}
      {streamMessages.length === 0 && debate.status === "pending" && (
        <div className="text-center py-16" style={{ color: "var(--sub)" }}>
          <Loader2 className="animate-spin mx-auto mb-3" size={36} />
          <p className="font-semibold">辩论准备中…</p>
          <p className="text-xs mt-1">AI 辩手即将开始发言</p>
        </div>
      )}

      {/* 评论区（辩论结束后显示） */}
      <CommentSection debateId={id} done={done} />
    </div>
  );
}
