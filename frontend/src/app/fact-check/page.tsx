"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Loader2, Search, ShieldCheck, Upload, FileText } from "lucide-react";

const AGENT_COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#06b6d4"];
const AGENT_EMOJIS = ["🔍", "🧠", "⏰", "📊", "🤖", "🔎"];
const SAMPLE_TEXT = `人工智能技术近年来发展迅速。据统计，2024年全球AI市场规模已超过5000亿美元，预计到2030年将突破10万亿美元。专家指出，AI将在未来十年内替代50%的人类工作岗位。然而，AI的发展也带来了伦理和安全方面的挑战。一方面，AI可以帮助人类解决复杂问题；另一方面，AI也可能被滥用造成危害。综上所述，我们需要在鼓励创新和加强监管之间找到平衡。`;

export default function FactCheckPage() {
  const [text, setText] = useState("");
  const [debateId, setDebateId] = useState<string | null>(null);
  const [state, setState] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");

  // 文件上传
  const handleFile = useCallback(async (file: File) => {
    if (!file.name.match(/\.(pdf|docx|txt|md|csv)$/i)) {
      setError("不支持的文件格式，支持 PDF、Word、TXT、MD"); return;
    }
    setUploading(true); setError(""); setUploadedFile("");
    try {
      const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const form = new FormData();
      form.append("file", file);
      const r = await fetch(`${BASE}/api/fact-check/upload`, { method: "POST", body: form });
      const data = await r.json();
      if (!r.ok) { setError(data.detail || "上传失败"); return; }
      setText(data.text);
      setUploadedFile(`${data.filename} (${data.length} 字${data.truncated ? "，已截断" : ""})`);
    } catch {
      setError("上传失败，请检查网络");
    } finally {
      setUploading(false);
    }
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  // 轮询核查进度
  useEffect(() => {
    if (!debateId) return;
    let timer: ReturnType<typeof setInterval>;
    let active = true;

    async function poll() {
      try {
        const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const r = await fetch(`${BASE}/api/debates/${debateId}/live`);
        if (!active) return;
        const s = await r.json();
        setState(s);
        if (s.status === "completed" || s.status === "failed") {
          clearInterval(timer);
          setLoading(false);
        }
      } catch { /* retry */ }
    }

    poll();
    timer = setInterval(poll, 1000);
    return () => { active = false; clearInterval(timer); };
  }, [debateId]);

  async function handleSubmit() {
    if (text.trim().length < 50) { setError("文本至少 50 字"); return; }
    setError(""); setLoading(true); setState(null);

    try {
      const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const r = await fetch(`${BASE}/api/fact-check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim() }),
      });
      const data = await r.json();
      setDebateId(data.debate_id);
    } catch {
      setError("提交失败，请重试");
      setLoading(false);
    }
  }

  const messages = state?.messages || [];
  const streaming = state?.streaming;
  const isRunning = state?.status === "running" || state?.status === "pending";
  const isDone = state?.status === "completed";

  // 合并流式文字
  const allMsgs: any[] = [...messages];
  if (streaming && streaming.text && isRunning) {
    const last = allMsgs[allMsgs.length - 1];
    if (!last || last.agent_name !== streaming.agent_name || last.round_num !== streaming.round_num) {
      allMsgs.push({ agent_name: streaming.agent_name, content: streaming.text, round_num: streaming.round_num, streaming: true });
    } else {
      allMsgs[allMsgs.length - 1] = { ...last, content: streaming.text, streaming: true };
    }
  }

  // 按轮次分组
  const rounds = new Set<number>();
  allMsgs.forEach((m: any) => rounds.add(m.round_num));
  const sortedRounds = Array.from(rounds).sort((a, b) => a - b);

  const ROUND_NAMES: Record<number, string> = {
    1: "独立审查",
    2: "交叉辩论",
    3: "裁判总结",
  };

  const agentIndexMap = useRef<Record<string, number>>({});
  if (state) {
    const names = new Set<string>();
    allMsgs.forEach((m: any) => names.add(m.agent_name));
    Array.from(names).forEach((n, i) => { agentIndexMap.current[n] = i; });
  }

  return (
    <div className="w-full max-w-4xl mx-auto px-1 sm:px-0">
      <h1 className="text-xl font-bold mb-2 flex items-center gap-2">
        <ShieldCheck size={24} style={{ color: "var(--accent)" }} />
        文本事实核查
      </h1>
      <p className="text-sm mb-6" style={{ color: "var(--sub)" }}>
        6 位 AI 审查员从事实、逻辑、时间、数据、AI 痕迹等维度分析文本，交叉辩论后由裁判给出最终报告。<br />
        支持粘贴文本或上传 Word / PDF 文件自动提取文字。
      </p>

      {/* 输入区 */}
      {!debateId && (
        <div className="mb-6">
          {/* 文件上传 */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            className={`p-3 rounded-lg border-2 border-dashed text-center cursor-pointer mb-3 transition-colors ${dragOver ? "opacity-80" : ""}`}
            style={{ borderColor: dragOver ? "var(--accent)" : "var(--border)", background: dragOver ? "var(--bg)" : "var(--card)" }}
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <input id="file-input" type="file" accept=".pdf,.docx,.txt,.md,.csv"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
              className="hidden" />
            {uploading ? (
              <div className="flex items-center justify-center gap-2 text-sm" style={{ color: "var(--sub)" }}>
                <Loader2 size={16} className="animate-spin" /> 解析文件中…
              </div>
            ) : uploadedFile ? (
              <div className="flex items-center justify-center gap-2 text-sm" style={{ color: "#10b981" }}>
                <FileText size={16} /> {uploadedFile}
              </div>
            ) : (
              <div style={{ color: "var(--sub)" }}>
                <Upload size={20} className="mx-auto mb-1 opacity-50" />
                <p className="text-sm m-0">上传 Word / PDF 文件自动提取文字</p>
                <p className="text-xs mt-0.5 opacity-60">或直接在下方粘贴文本</p>
              </div>
            )}
          </div>

          <textarea value={text} onChange={(e) => setText(e.target.value)}
            placeholder="粘贴需要核查的文本，或上传文件自动填充（至少 50 字）…"
            rows={8}
            className="w-full p-3 rounded-lg border text-sm resize-y"
            style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }} />
          <p className="text-xs mt-1" style={{ color: "var(--sub)" }}>
            {text.length} 字
            <button onClick={() => setText(SAMPLE_TEXT)}
              className="ml-2 bg-transparent border-0 cursor-pointer" style={{ color: "var(--accent)" }}>
              填入示例文本
            </button>
          </p>
          {error && <p className="text-red-500 text-xs mt-2">{error}</p>}
          <button onClick={handleSubmit} disabled={loading || text.trim().length < 50}
            className="mt-3 px-6 py-2.5 rounded-lg text-white font-semibold border-0 cursor-pointer disabled:opacity-50 flex items-center gap-2"
            style={{ background: loading ? "var(--sub)" : "var(--accent)" }}>
            <Search size={18} /> {loading ? "提交中…" : "开始核查"}
          </button>
        </div>
      )}

      {/* 进度 */}
      {loading && !state && (
        <div className="text-center py-16" style={{ color: "var(--sub)" }}>
          <Loader2 className="animate-spin mx-auto mb-3" size={36} />
          <p className="font-semibold">正在启动审查引擎…</p>
        </div>
      )}

      {/* 结果展示 */}
      {state && (
        <div>
          <div className="p-3 rounded-lg mb-4" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
            <div className="flex items-center gap-3 text-xs" style={{ color: "var(--sub)" }}>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full animate-pulse"
                  style={{ background: isRunning ? "#10b981" : "var(--accent)" }} />
                {isRunning ? `核查中 (${messages.length} 条分析)` : `已完成 (${messages.length} 条分析)`}
              </span>
            </div>
          </div>

          {sortedRounds.map((r) => {
            const roundMsgs = allMsgs.filter((m: any) => m.round_num === r);
            return (
              <div key={r}>
                <div className="text-center py-4 text-xs font-bold tracking-wider" style={{ color: "var(--accent)" }}>
                  ━━ 第 {r} 阶段：{ROUND_NAMES[r] || `第${r}轮`} ━━
                </div>
                {roundMsgs.map((msg: any, mi: number) => {
                  const idx = agentIndexMap.current[msg.agent_name] || 0;
                  const cl = AGENT_COLORS[idx % 6];
                  const em = idx < 6 ? AGENT_EMOJIS[idx] : "⚖️";

                  return (
                    <div key={`${r}-${mi}`} className="flex gap-2 sm:gap-3 py-2.5 sm:py-3" style={{ borderBottom: "1px solid var(--border)" }}>
                      <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg sm:rounded-xl flex items-center justify-center text-white flex-shrink-0 text-xs sm:text-base"
                        style={{ background: cl }}>{em}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                          <span className="font-bold text-xs sm:text-sm" style={{ color: cl }}>{msg.agent_name}</span>
                          {msg.streaming && <span className="text-[10px] animate-pulse" style={{ color: "var(--accent)" }}>分析中…</span>}
                        </div>
                        <div className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap break-words">
                          {msg.content}
                          {msg.streaming && <span className="animate-pulse" style={{ color: "var(--accent)" }}>▌</span>}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })}

          {isDone && (
            <div className="text-center mt-6">
              <button onClick={() => { setDebateId(null); setState(null); setText(""); }}
                className="px-4 py-2 rounded-lg text-sm border cursor-pointer"
                style={{ borderColor: "var(--accent)", color: "var(--accent)", background: "transparent" }}>
                核查新文本
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
