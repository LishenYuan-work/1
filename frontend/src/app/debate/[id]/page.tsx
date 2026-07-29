"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import { debates, type DebateDetail, type MessageItem } from "@/lib/api";
import { Send, Loader2 } from "lucide-react";
import CommentSection from "@/components/CommentSection";

const AGENT_COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#06b6d4"];
const AGENT_EMOJIS = ["🎓", "⚖️", "🔬", "💡", "🌍", "🔍"];

const ROUND_LABELS = (r: number, total: number) =>
  r === 1 ? "开场陈述" : r === total ? "总结陈词" : "自由辩论";

export default function DebatePage() {
  const { id } = useParams<{ id: string }>();
  const [debate, setDebate] = useState<DebateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [followQ, setFollowQ] = useState<Record<number, string>>({});
  const [followReply, setFollowReply] = useState<Record<number, string>>({});
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevCountRef = useRef(0);

  // 核心：轮询拉取新消息（每 2 秒）
  const poll = useCallback(async () => {
    try {
      const d = await debates.get(id);
      setDebate((prev) => {
        // 有新消息或状态变化才更新
        if (!prev || d.messages.length !== prev.messages.length || d.status !== prev.status) {
          return d;
        }
        return prev;
      });
      // 辩论结束，停止轮询
      if (d.status === "completed" || d.status === "failed") {
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      }
    } catch {
      // 网络错误，继续重试
    }
  }, [id]);

  useEffect(() => {
    // 首次加载
    debates.get(id).then((d) => {
      setDebate(d);
      setLoading(false);
      prevCountRef.current = d.messages.length;

      // 如果未完成，开始轮询
      if (d.status !== "completed" && d.status !== "failed") {
        pollRef.current = setInterval(poll, 2000);
      }
    }).catch(() => setLoading(false));

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [id]);

  const agentIndexMap = useRef<Record<string, number>>({});
  if (debate) {
    debate.agents.forEach((a, i) => { agentIndexMap.current[a.name] = i; });
  }

  const messages = debate?.messages || [];
  const isRunning = debate?.status === "running" || debate?.status === "pending";
  const isDone = debate?.status === "completed" || debate?.status === "failed";

  // 按轮次分组
  const rounds = new Set<number>();
  for (const m of messages) rounds.add(m.round_num);
  const sortedRounds = Array.from(rounds).sort((a, b) => a - b);

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

  return (
    <div className="w-full max-w-4xl mx-auto px-0 sm:px-1">
      {/* 头部 */}
      <div className="p-3 sm:p-4 rounded-xl mb-4 sm:mb-6" style={{ background: "var(--card)", borderLeft: "4px solid var(--accent)" }}>
        <span className="text-xs" style={{ color: "var(--sub)" }}>辩论话题</span>
        <h1 className="text-lg font-bold m-0 mt-1">{debate.topic}</h1>
        <div className="flex items-center gap-3 mt-2 text-xs" style={{ color: "var(--sub)" }}>
          <span>{debate.agents.length} 位辩手</span><span>·</span><span>{debate.rounds} 轮</span><span>·</span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full animate-pulse"
              style={{ background: isRunning ? "#10b981" : isDone ? "var(--accent)" : "var(--sub)" }} />
            {isRunning ? `辩论中 (${messages.length} 条发言)` : isDone ? `已完成 (${messages.length} 条发言)` : debate.status}
          </span>
        </div>
      </div>

      {/* 空状态 */}
      {messages.length === 0 && isRunning && (
        <div className="text-center py-16" style={{ color: "var(--sub)" }}>
          <Loader2 className="animate-spin mx-auto mb-3" size={36} />
          <p className="font-semibold">AI 辩手准备中…</p>
          <p className="text-xs mt-1">辩论即将开始，新发言会自动出现</p>
        </div>
      )}

      {/* 消息流 */}
      {sortedRounds.map((r) => {
        const roundMsgs = messages.filter((m) => m.round_num === r);
        return (
          <div key={r}>
            <div className="text-center py-4 text-xs font-bold tracking-wider" style={{ color: "var(--accent)" }}>
              ━━ 第 {r}/{debate.rounds} 轮 · {ROUND_LABELS(r, debate.rounds)} ━━
            </div>
            {roundMsgs.map((msg: MessageItem, mi: number) => {
              const idx = agentIndexMap.current[msg.agent_name] || 0;
              const cl = AGENT_COLORS[idx % 6];
              const em = AGENT_EMOJIS[idx % 6];
              const globalIdx = messages.indexOf(msg);

              return (
                <div key={`${r}-${mi}`} className="flex gap-2 sm:gap-3 py-2.5 sm:py-3" style={{ borderBottom: "1px solid var(--border)" }}>
                  <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg sm:rounded-xl flex items-center justify-center text-white flex-shrink-0 text-xs sm:text-base"
                    style={{ background: cl }}>{em}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 sm:gap-2 mb-1 flex-wrap">
                      <span className="font-bold text-xs sm:text-sm" style={{ color: cl }}>{msg.agent_name}</span>
                      <span className="text-[10px] sm:text-xs px-1.5 py-0.5 rounded-md"
                        style={{ color: "var(--sub)", background: "var(--bg)" }}>第{r}轮</span>
                    </div>
                    <div className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap break-words">{msg.content}</div>

                    {isDone && (
                      <div className="mt-2">
                        <button onClick={() => {
                          const newState = { ...followQ };
                          if (newState[globalIdx] === undefined) newState[globalIdx] = "";
                          else delete newState[globalIdx];
                          setFollowQ(newState);
                        }}
                          className="text-xs bg-transparent border-0 cursor-pointer"
                          style={{ color: "var(--sub)" }}>💬 追问</button>
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
                              style={{ background: "var(--accent)" }}><Send size={12} /></button>
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
        );
      })}

      <CommentSection debateId={id} done={isDone} />
    </div>
  );
}
