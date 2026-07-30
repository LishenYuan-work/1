"use client";

import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { debates, type LiveState, type MessageItem } from "@/lib/api";
import { Send, Loader2 } from "lucide-react";
import CommentSection from "@/components/CommentSection";

const AGENT_COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#06b6d4"];
const AGENT_EMOJIS = ["🎓", "⚖️", "🔬", "💡", "🌍", "🔍"];
const ROUND_LABELS = (r: number, total: number) =>
  r === 1 ? "开场陈述" : r === total ? "总结陈词" : "自由辩论";

function DebateContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") || "";
  const [state, setState] = useState<LiveState | null>(null);
  const [loading, setLoading] = useState(true);
  const [followQ, setFollowQ] = useState<Record<number, string>>({});
  const [followReply, setFollowReply] = useState<Record<number, string>>({});

  // 每秒轮询 /live 端点
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setInterval>;

    async function tick() {
      try {
        const s = await debates.live(id);
        if (!active) return;
        setState(s);
        setLoading(false);
        if (s.status === "completed" || s.status === "failed") {
          clearInterval(timer);
        }
      } catch {
        // 网络错误，继续重试
      }
    }

    tick(); // 立即执行第一次
    timer = setInterval(tick, 500); // 0.5秒轮询，更流畅的逐字效果
    return () => { active = false; clearInterval(timer); };
  }, [id]);

  const agentIndexMap = useRef<Record<string, number>>({});
  if (state) {
    // 从消息和流式状态中收集所有 agent 名字
    const agentNames = new Set<string>();
    state.messages.forEach((m) => agentNames.add(m.agent_name));
    if (state.streaming) agentNames.add(state.streaming.agent_name);
    Array.from(agentNames).forEach((name, i) => { agentIndexMap.current[name] = i; });
  }

  const messages = state?.messages || [];
  const streaming = state?.streaming;
  const isRunning = state?.status === "running" || state?.status === "pending";
  const isDone = state?.status === "completed" || state?.status === "failed";

  // 合并消息和流式文本
  const allMessages: (MessageItem & { streaming?: boolean })[] = [...messages];
  if (streaming && streaming.text) {
    const lastMsg = messages[messages.length - 1];
    // 如果最后一条消息不是当前 agent 在同一轮，追加流式条目
    if (!lastMsg || lastMsg.agent_name !== streaming.agent_name || lastMsg.round_num !== streaming.round_num) {
      allMessages.push({
        agent_name: streaming.agent_name,
        content: streaming.text,
        round_num: streaming.round_num,
        streaming: true,
      });
    } else {
      // 替换最后一条为流式版本
      allMessages[allMessages.length - 1] = {
        ...lastMsg,
        content: streaming.text,
        streaming: true,
      };
    }
  }

  // 按轮次分组
  const rounds = new Set<number>();
  for (const m of allMessages) rounds.add(m.round_num);
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

  if (loading) return <div className="text-center py-20" style={{ color: "var(--sub)" }}><Loader2 className="animate-spin mx-auto" size={32} />加载中…</div>;
  if (!state) return <div className="text-center py-20" style={{ color: "var(--sub)" }}>辩论不存在</div>;

  return (
    <div className="w-full max-w-4xl mx-auto px-0 sm:px-1">
      {/* 头部 */}
      <div className="p-3 sm:p-4 rounded-xl mb-4 sm:mb-6" style={{ background: "var(--card)", borderLeft: "4px solid var(--accent)" }}>
        <span className="text-xs" style={{ color: "var(--sub)" }}>辩论话题</span>
        <h1 className="text-lg font-bold m-0 mt-1">{state.messages.length > 0 ? `辩论进行中 (${state.messages.length} 条发言)` : '准备开始…'}</h1>
        <div className="flex items-center gap-3 mt-2 text-xs" style={{ color: "var(--sub)" }}>
          <span>{agentIndexMap.current ? Object.keys(agentIndexMap.current).length : 0} 位辩手</span><span>·</span>
          <span>{sortedRounds.length > 0 ? sortedRounds[sortedRounds.length - 1] : '?'} / {3} 轮</span><span>·</span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full animate-pulse"
              style={{ background: isRunning ? "#10b981" : isDone ? "var(--accent)" : "var(--sub)" }} />
            {isRunning ? `辩论中 (${messages.length} 条发言)` : isDone ? `已完成 (${messages.length} 条发言)` : state.status}
          </span>
        </div>
      </div>

      {/* 空状态 */}
      {allMessages.length === 0 && isRunning && (
        <div className="text-center py-16" style={{ color: "var(--sub)" }}>
          <Loader2 className="animate-spin mx-auto mb-3" size={36} />
          <p className="font-semibold">AI 辩手准备中…</p>
          <p className="text-xs mt-1">发言将逐字实时展示</p>
        </div>
      )}

      {/* 消息流 */}
      {sortedRounds.map((r) => {
        const roundMsgs = allMessages.filter((m) => m.round_num === r);
        return (
          <div key={r}>
            <div className="text-center py-4 text-xs font-bold tracking-wider" style={{ color: "var(--accent)" }}>
              ━━ 第 {r} 轮 · {ROUND_LABELS(r, sortedRounds[sortedRounds.length - 1] || 3)} ━━
            </div>
            {roundMsgs.map((msg, mi) => {
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
                      {msg.streaming && (
                        <span className="text-[10px] sm:text-xs animate-pulse" style={{ color: "var(--accent)" }}>
                          输入中…
                        </span>
                      )}
                    </div>
                    <div className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap break-words">
                      {msg.content}
                      {msg.streaming && <span className="animate-pulse" style={{ color: "var(--accent)" }}>▌</span>}
                    </div>

                    {!msg.streaming && isDone && (
                      <div className="mt-2">
                        <button onClick={() => {
                          const newState = { ...followQ };
                          if (newState[globalIdx] === undefined) newState[globalIdx] = "";
                          else delete newState[globalIdx];
                          setFollowQ(newState);
                        }} className="text-xs bg-transparent border-0 cursor-pointer" style={{ color: "var(--sub)" }}>💬 追问</button>
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

export default function DebatePage() {
  return (
    <Suspense fallback={<div className="text-center py-20" style={{ color: "var(--sub)" }}><Loader2 className="animate-spin mx-auto" size={32} />加载中…</div>}>
      <DebateContent />
    </Suspense>
  );
}
