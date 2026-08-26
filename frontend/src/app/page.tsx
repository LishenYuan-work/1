"use client";
import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  FileText,
  LogOut,
  Play,
  Plus,
  ShieldCheck,
  Upload,
  Download,
  CircleHelp,
  Trash2,
} from "lucide-react";
import {
  api,
  type EvidenceItem,
  type ReviewDetail,
  type ReviewEvent,
  type ReviewSummary,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useReviewStream } from "@/lib/use-sse";
import Link from "next/link";

const labels: Record<string, string> = {
  document_parse: "文档解析 Agent",
  benefit_argument: "收益论证 Agent",
  risk_argument: "风险研判 Agent",
  fact_check: "事实核查 Agent",
  summary_report: "汇总评审 Agent",
};
const stages = [
  "document_parse",
  "benefit_argument",
  "risk_argument",
  "fact_check",
  "summary_report",
];
const statusLabels: Record<string, string> = {
  completed: "已完成",
  failed: "失败",
  running: "进行中",
  queued: "排队中",
  awaiting_human: "待人工复核",
  needs_revision: "需重新评审",
  interrupted: "已暂停",
};

export default function HomePage() {
  const { user, loading, logout } = useAuth();
  const [organization, setOrganization] = useState("");
  const [reviews, setReviews] = useState<ReviewSummary[]>([]);
  const [selected, setSelected] = useState<ReviewDetail | null>(null);
  const [topic, setTopic] = useState("");
  const [rounds, setRounds] = useState(3);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [events, setEvents] = useState<ReviewEvent[]>([]);
  const [streamContent, setStreamContent] = useState<Record<string, string>>({});
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteMessage, setInviteMessage] = useState("");
  const [humanBusy, setHumanBusy] = useState(false);
  const selectedRef = useRef<ReviewDetail | null>(null);
  const orgRef = useRef<string | undefined>(undefined);
  const activeOrg = useMemo(
    () =>
      user?.organizations.find((o) => o.id === organization) ||
      user?.organizations[0],
    [organization, user],
  );
  useEffect(() => { selectedRef.current = selected; }, [selected]);
  useEffect(() => { orgRef.current = activeOrg?.id; }, [activeOrg?.id]);
  useEffect(() => {
    if (activeOrg)
      api.reviews
        .list(activeOrg.id)
        .then(setReviews)
        .catch((err) => setError(err.message));
  }, [activeOrg]);
  const onEvent = useCallback(
    (event: ReviewEvent) => {
      setEvents((prev) => [
        ...prev.filter((e) => e.sequence !== event.sequence),
        event,
      ]);
      if (event.type === "agent_chunk" && typeof event.agent === "string" && typeof event.content === "string") {
        setStreamContent((prev) => ({ ...prev, [event.agent as string]: `${prev[event.agent as string] || ""}${event.content as string}` }));
      }
      if (event.type === "agent_result" && typeof event.agent === "string") {
        setStreamContent((prev) => { const next = { ...prev }; delete next[event.agent as string]; return next; });
      }
      const current = selectedRef.current;
      const orgId = orgRef.current;
      if (event.type === "done" || event.type === "report_ready" || event.type === "session_status" || event.type === "agent_result") {
        if (current) api.reviews.get(current.id, orgId).then((detail) => { selectedRef.current = detail; setSelected(detail); });
      }
      if (event.type === "evidence_upsert" && current)
        api.reviews.evidence(current.id, orgId).then(setEvidence);
    },
    [],
  );
  const { connect, connected } = useReviewStream(selected?.id || null, onEvent);
  async function createReview() {
    if (!activeOrg || (!topic.trim() && files.length === 0)) {
      setError("请输入调研主题或上传至少一个文档");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const review = await api.reviews.create({
        organization_id: activeOrg.id,
        topic: topic.trim() || undefined,
        max_round: rounds,
      });
      for (const file of files)
        await api.reviews.upload(review.id, file, activeOrg.id);
      const detail = await api.reviews.get(review.id, activeOrg.id);
      setSelected(detail);
      setStreamContent({});
      setReviews((prev) => [review, ...prev]);
      setTopic("");
      setFiles([]);
      await api.reviews.start(review.id, activeOrg.id);
      connect(review.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建评审失败");
    } finally {
      setBusy(false);
    }
  }
  async function selectReview(id: string) {
    if (!activeOrg) return;
    try {
      const detail = await api.reviews.get(id, activeOrg.id);
      setSelected(detail);
      setEvents([]);
      setStreamContent({});
      setEvidence(await api.reviews.evidence(id, activeOrg.id));
      if (
        detail.status === "running" ||
        detail.status === "queued" ||
        detail.status === "interrupted"
      )
        connect(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载评审失败");
    }
  }
  async function downloadReport() {
    if (!selected) return;
    const response = await fetch(api.reviews.downloadUrl(selected.id), {
      credentials: "include",
    });
    if (!response.ok) {
      setError(response.status === 401 ? "登录已过期，请重新登录" : "报告下载失败");
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `review-${selected.id.slice(0, 8)}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
  async function humanReview(approved: boolean) {
    if (!selected || !activeOrg) return;
    setHumanBusy(true);
    try {
      await api.reviews.humanReview(selected.id, approved, undefined, activeOrg.id);
      const detail = await api.reviews.get(selected.id, activeOrg.id);
      setSelected(detail);
      if (approved) connect(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "人工复核提交失败");
    } finally {
      setHumanBusy(false);
    }
  }
  async function deleteReview() {
    if (!selected || !activeOrg || !window.confirm("确定删除这个评审任务吗？此操作不可撤销。")) return;
    try {
      await api.reviews.delete(selected.id, activeOrg.id);
      setReviews((prev) => prev.filter((item) => item.id !== selected.id));
      setSelected(null);
      setEvidence([]);
      setEvents([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除评审失败");
    }
  }
  async function inviteMember() {
    if (!activeOrg || !inviteEmail.trim()) return;
    try {
      await api.organizations.invite(activeOrg.id, inviteEmail.trim());
      setInviteMessage("邀请已发送");
      setInviteEmail("");
    } catch (err) {
      setInviteMessage(err instanceof Error ? err.message : "邀请失败");
    }
  }
  function addFiles(e: ChangeEvent<HTMLInputElement>) {
    const next = Array.from(e.target.files || []);
    const invalidType = next.find((file) => !/\.(pdf|docx)$/i.test(file.name));
    const oversized = next.find((file) => file.size > 20 * 1024 * 1024);
    if (invalidType) {
      setError(`不支持文件格式：${invalidType.name}`);
      return;
    }
    if (oversized) {
      setError(`文件超过 20 MB：${oversized.name}`);
      return;
    }
    if (files.length + next.length > 5) {
      setError("每个评审最多上传 5 个文件");
      return;
    }
    setError("");
    setFiles((prev) => [...prev, ...next]);
    e.target.value = "";
  }
  if (loading) return <div className="empty">正在加载工作区</div>;
  if (!user)
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div className="brand">
            <span className="brand-mark">R</span> 多 Agent 交叉评审
          </div>
          <h1>方案交叉评审</h1>
          <p>围绕方案、立项文档和调研主题，形成带证据溯源的结构化评审报告。</p>
          <Link
            className="primary"
            style={{ display: "inline-block", textDecoration: "none" }}
            href="/login"
          >
            登录工作台
          </Link>
        </section>
      </main>
    );
  return (
    <div className="review-shell">
      <aside className="review-sidebar">
        <div className="brand">
          <span className="brand-mark">R</span>
          <span>交叉评审</span>
        </div>
        <div className="sidebar-section">
          <h2>组织工作区</h2>
          <select
            className="select org-switcher"
            value={activeOrg?.id || ""}
            onChange={(e) => setOrganization(e.target.value)}
          >
            {user.organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </select>
          {activeOrg?.role === "owner" && (
            <div className="field" style={{ marginTop: 8 }}>
              <label htmlFor="invite">邀请成员</label>
              <input
                id="invite"
                className="input"
                type="email"
                placeholder="同事邮箱"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
              <button className="secondary" onClick={inviteMember}>
                发送邀请
              </button>
              {inviteMessage && <small>{inviteMessage}</small>}
            </div>
          )}
        </div>
        <div className="sidebar-section">
          <h2>评审历史</h2>
          {reviews.length === 0 ? (
            <div
              style={{ padding: "10px", color: "var(--muted)", fontSize: 12 }}
            >
              暂无评审任务
            </div>
          ) : (
            reviews.map((item) => (
              <button
                key={item.id}
                className={`history-item ${selected?.id === item.id ? "active" : ""}`}
                onClick={() => selectReview(item.id)}
              >
                <strong>{item.topic || "未命名文档评审"}</strong>
                <span>
                  {statusLabels[item.status] || "草稿"}{" "}
                  · {new Date(item.created_at).toLocaleDateString("zh-CN")}
                </span>
              </button>
            ))
          )}
        </div>
        <div className="sidebar-footer">
          <div style={{ marginBottom: 9 }}>{user.email}</div>
          <button onClick={logout}>
            <LogOut
              size={14}
              style={{ verticalAlign: "-2px", marginRight: 5 }}
            />
            退出登录
          </button>
        </div>
      </aside>
      <main className="review-main">
        <header className="topbar">
          <div>
            <h1>{selected?.topic || "新建评审任务"}</h1>
            <p>
              {activeOrg?.name} · {connected ? "实时连接中" : "准备就绪"}
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="status">
              <span className={`status-dot ${connected ? "live" : ""}`} />
              {selected?.status || "草稿"}
            </span>
            {selected && (activeOrg?.role === "owner" || selected.creator_id === user.id) && (
              <button className="secondary" onClick={deleteReview} title="删除评审">
                <Trash2 size={14} style={{ verticalAlign: "-2px", marginRight: 5 }} />删除
              </button>
            )}
          </div>
        </header>
        <div className="content grid">
          <section className="panel">
            <div className="panel-head">
              <div>
                <div className="panel-title">输入评审材料</div>
                <div className="panel-meta">输入主题，或上传方案与立项文档</div>
              </div>
              <CircleHelp size={16} color="var(--muted)" />
            </div>
            <div className="composer">
              <div className="grid">
                <div className="field">
                  <label htmlFor="topic">调研主题</label>
                  <textarea
                    id="topic"
                    className="textarea"
                    placeholder="例如：评估企业知识库升级方案的收益、风险与实施约束"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                  />
                </div>
                <div className="composer-actions">
                  <span style={{ color: "var(--muted)", fontSize: 12 }}>
                    最多 5 个 PDF 或 DOCX，每个不超过 20 MB
                  </span>
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={createReview}
                  >
                    <Play
                      size={15}
                      style={{ verticalAlign: "-2px", marginRight: 6 }}
                    />
                    {busy ? "准备评审中" : "启动评审"}
                  </button>
                </div>
              </div>
              <div className="grid">
                <div className="field">
                  <label htmlFor="rounds">评审轮次</label>
                  <select
                    id="rounds"
                    className="select"
                    value={rounds}
                    onChange={(e) => setRounds(Number(e.target.value))}
                  >
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n} 轮
                      </option>
                    ))}
                  </select>
                </div>
                <div className="dropzone">
                  <Upload size={18} />
                  <div style={{ marginTop: 8 }}>添加 PDF / DOCX</div>
                  <input
                    type="file"
                    accept=".pdf,.docx"
                    multiple
                    onChange={addFiles}
                  />
                </div>
                {files.length > 0 && (
                  <div className="file-list">
                    {files.map((file, index) => (
                      <div className="file-row" key={`${file.name}-${index}`}>
                        <span>
                          <FileText
                            size={13}
                            style={{ verticalAlign: "-2px", marginRight: 5 }}
                          />
                          {file.name}
                        </span>
                        <button
                          className="text-button"
                          onClick={() =>
                            setFiles(files.filter((_, i) => i !== index))
                          }
                        >
                          移除
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <div className="panel-title">Agent 工作流</div>
                <div className="panel-meta">
                  每条输出会进入证据池并绑定检索来源
                </div>
              </div>
              <span className="status">
                <span className={`status-dot ${connected ? "live" : ""}`} />
                {selected
                  ? `${selected.current_round} / ${selected.max_round} 轮`
                  : "等待启动"}
              </span>
            </div>
            <div className="agents">
              {stages.map((stage, index) => {
                const latest = [...(selected?.outputs || [])]
                  .reverse()
                  .find((output) => output.agent_role === stage);
                const activeRound = latest?.round_num ?? selected?.current_round ?? 0;
                const lastStart = [...events].reverse().find((event) => event.type === "agent_start" && event.agent === stage && (Number(event.round || 0) === activeRound || stage === "document_parse"));
                const lastResult = [...events].reverse().find((event) => (event.type === "agent_result" && event.agent === stage) || (stage === "fact_check" && event.type === "evidence_upsert" && event.agent === "fact_check" && event.verdict));
                const live = Boolean(lastStart && (!lastResult || lastStart.sequence > lastResult.sequence));
                return (
                  <article className="agent-row" key={stage}>
                    <div className="agent-icon">A{index + 1}</div>
                    <div>
                      <h3>{labels[stage]}</h3>
                      <p>
                        {latest?.content_markdown || streamContent[stage] ||
                          (live
                            ? "正在处理当前材料..."
                            : stage === "fact_check"
                              ? "等待论据输出后检索并绑定来源"
                              : "等待上游阶段完成")}
                      </p>
                    </div>
                    <div className="agent-side">
                      {live ? "处理中" : latest ? "已完成" : "排队中"}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <div className="panel-title">证据池</div>
                <div className="panel-meta">每条论据的核查状态与来源链接</div>
              </div>
              <ShieldCheck size={17} color="var(--accent)" />
            </div>
            {evidence.length === 0 ? (
              <div className="empty">
                评审启动后，事实核查 Agent 会在这里记录证据。
              </div>
            ) : (
              <div className="evidence-list">
                {evidence.map((item) => (
                  <article className="evidence-item" key={item.id}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 10,
                      }}
                    >
                      <strong>{item.claim_text}</strong>
                      <span className={`verdict ${item.verdict}`}>
                        {item.verdict === "verified"
                          ? "已核实"
                          : item.verdict === "contradicted"
                            ? "有冲突"
                            : "待确认"}
                      </span>
                    </div>
                    <details>
                      <summary>查看 {item.sources.length} 个来源</summary>
                      <p>{item.rationale}</p>
                      {item.sources.map((source) => (
                        <a
                          key={source.id}
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {source.title}
                        </a>
                      ))}
                    </details>
                  </article>
                ))}
              </div>
            )}
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <div className="panel-title">评审报告</div>
                <div className="panel-meta">完成后生成五段式 Markdown 报告</div>
              </div>
              {selected?.status === "awaiting_human" && (
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="secondary" disabled={humanBusy} onClick={() => humanReview(false)}>暂不通过</button>
                  <button className="primary" disabled={humanBusy} onClick={() => humanReview(true)}>确认生成报告</button>
                </div>
              )}
              {selected?.report_markdown && (
                <button className="secondary" onClick={downloadReport}>
                  <Download
                    size={14}
                    style={{ verticalAlign: "-2px", marginRight: 5 }}
                  />
                  下载 Markdown
                </button>
              )}
            </div>
            {selected?.report_markdown ? (
              <div className="report">{selected.report_markdown}</div>
            ) : (
              <div className="empty">报告将在汇总评审 Agent 完成后展示。</div>
            )}
          </section>
          {error && <div className="error">{error}</div>}
          <div
            style={{
              color: "var(--muted)",
              fontSize: 11,
              display: "flex",
              gap: 8,
              alignItems: "center",
            }}
          >
            <Plus size={13} />
            团队成员可在组织设置中通过邮件邀请加入同一评审空间。
          </div>
        </div>
      </main>
    </div>
  );
}
