"use client";

import { useEffect, useState, useRef, useMemo } from "react";
import { useParams } from "next/navigation";
import { debates, type DebateDetail } from "@/lib/api";
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
  const [pollInterval, setPollInterval] = useState<ReturnType<typeof setInterval> | null>(null);

  // 建立 SSE 连接
  const { events, connected, done, connect } = useDebateStream(id);

  // 页面加载：获取辩论信息
  useEffect(() => {
    debates.get(id).then((d) => {
      setDebate(d);
      setLoading(false);

      // 如果辩论还在运行中，连接 SSE
      if (d.status === "pending" || d.status === "running") {
        connect();
      }
    }).catch(() => setLoading(false));
  }, [id]);

  // 如果辩论运行中但 SSE 断开了，定时刷新以获取完成状态
  useEffect(() => {
    if (connected || !debate || debate.status === "completed" || debate.status === "failed") return;
    if (done) {
      // SSE 报告完成，刷新页面数据
      debates.get(id).then(setDebate);
      return;
    }

    // 轮询兜底：每 5 秒检查一次
    const t = setInterval(() => {
      debates.get(id).then((d) => {
        setDebate(d);
        if (d.status === "completed" || d.status === "failed") {
          clearInterval(t);
        }
      });
    }, 5000);
    setPollInterval(t);
    return () => clearInterval(t);
  }, [connected, done, debate?.status]);

  // SSE 事件处理完毕
  useEffect(() => {
    if (done) {
      // 刷新拿到完整数据
      debates.get(id).then(setDebate);
      if (pollInterval) clearInterval(pollInterval);
    }
  }, [done]);

  // 构建 Agent 颜色索引
  const agentIndexMap = useRef<Record<string, number>>({});
  if (debate) {
    debate.agents.forEach((a, i) => { agentIndexMap.current[a.name] = i; });
  }
  // 为 SSE 中新出现的 agent 分配索引
  for (const ev of events) {
    if ((ev.type === "agent_start" || ev.type === "chunk" || ev.type === "agent_end") && !(ev.agent in agentIndexMap.current)) {
      agentIndexMap.current[ev.agent] = Object.keys(agentIndexMap.current).length;
    }
  }

  // 合并消息：已有消息 + SSE 实时流
  const allMessages = useMemo(() => {
    const existing = debate?.messages || [];
    const result = [...existing];

    // 从 SSE 事件中提取正在流式输入的发言
    const streamingContent: Record<string, { round: number; text: string; done: boolean }> = {};

    for (const ev of events) {
      if (ev.type === "agent_start") {
        if (!streamingContent[ev.agent]) {
          streamingContent[ev.agent] = { round: ev.round, text: "", done: false };
        }
      }
      if (ev.type === "chunk") {
        if (!streamingContent[ev.agent]) {
          streamingContent[ev.agent] = { round: ev.round, text: "", done: false };
        }
        streamingContent[ev.agent].text += ev.text;
      }
      if (ev.type === "agent_end") {
        if (!streamingContent[ev.agent]) {
          streamingContent[ev.agent] = { round: ev.round, text: "", done: false };
        }
        streamingContent[ev.agent].text = ev.full_text;
        streamingContent[ev.agent].done = true;
      }
    }

    // 把流式内容追加到消息列表（如果消息列表里还没有这个发言）
    for (const [agent, info] of Object.entries(streamingContent)) {
      if (info.text && !existing.some((m) => m.agent_name === agent && m.round_num === info.round)) {
        result.push({
          agent_name: agent,
          content: info.text,
          round_num: info.round,
          streaming: !info.done,
        } as any);
      }
    }

    return result;
  }, [debate?.messages, events]);

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

  // 按轮次分组
  const rounds = new Set<number>();
  for (const m of allMessages) rounds.add(m.round_num);
  for (const ev of events) {
    if (ev.type === "round_start") rounds.add(ev.round);
  }
  const sortedRounds = Array.from(rounds).sort((a, b) => a - b);

  const isLive = debate.status === "running" || debate.status === "pending";

  return (
    <div className="w-full max-w-4xl mx-auto px-0 sm:px-1">
      {/* 头部 */}
      <div className="p-3 sm:p-4 rounded-xl mb-4 sm:mb-6" style={{ background: "var(--card)", borderLeft: "4px solid var(--accent)" }}>
        <span className="text-xs" style={{ color: "var(--sub)" }}>辩论话题</span>
        <h1 className="text-lg font-bold m-0 mt-1">{debate.topic}</h1>
        <div className="flex items-center gap-3 mt-2 text-xs" style={{ color: "var(--sub)" }}>
          <span>{debate.agents.length} 位辩手</span><span>·</span><span>{debate.rounds} 轮</span><span>·</span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full"
              style={{ background: connected ? "#10b981" : isLive ? "#f59e0b" : done || debate.status === "completed" ? "var(--accent)" : "var(--sub)" }} />
            {connected ? "直播中" : isLive ? "等待中…" : done || debate.status === "completed" ? "已完成" : debate.status === "failed" ? "失败" : debate.status}
          </span>
        </div>
      </div>

      {/* 消息流 */}
      {sortedRounds.length === 0 && isLive && (
        <div className="text-center py-16" style={{ color: "var(--sub)" }}>
          <Loader2 className="animate-spin mx-auto mb-3" size={36} />
          <p className="font-semibold">AI 辩手准备中…</p>
          <p className="text-xs mt-1">辩论即将开始，请稍候</p>
        </div>
      )}

      {sortedRounds.map((r) => {
        const roundMsgs = allMessages.filter((m: any) => m.round_num === r);
        return (
          <div key={r}>
            <div className="text-center py-4 text-xs font-bold tracking-wider" style={{ color: "var(--accent)" }}>
              ━━ 第 {r}/{debate.rounds} 轮 · {ROUND_LABELS(r, debate.rounds)} ━━
            </div>
            {roundMsgs.map((msg: any, mi: number) => {
              const idx = agentIndexMap.current[msg.agent_name] || 0;
              const cl = AGENT_COLORS[idx % 6];
              const em = AGENT_EMOJIS[idx % 6];
              const globalIdx = allMessages.indexOf(msg);

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

                    {!msg.streaming && !isLive && (
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

      {/* 评论区 */}
      <CommentSection debateId={id} done={done || debate.status === "completed"} />
    </div>
  );
}
