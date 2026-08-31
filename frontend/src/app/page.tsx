"use client";

import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Database,
  Download,
  ExternalLink,
  FileText,
  Gauge,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  Menu,
  Play,
  Plus,
  RefreshCw,
  Search,
  Save,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Timer,
  Trash2,
  Upload,
  Users,
  Workflow,
  X,
} from "lucide-react";
import Link from "next/link";
import { api, type EvidenceItem, type ReviewDetail, type ReviewEvent, type ReviewSummary } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useReviewStream } from "@/lib/use-sse";

type ViewKey = "review" | "orchestration" | "evidence" | "settings";

const labels: Record<string, string> = {
  document_parse: "文档解析 Agent",
  benefit_argument: "收益论证 Agent",
  risk_argument: "风险研判 Agent",
  fact_check: "事实核查 Agent",
  summary_report: "汇总评审 Agent",
};

const stageCards = [
  { key: "document_parse", title: "文档解析", detail: "提取观点、指标与约束", icon: FileText },
  { key: "benefit_argument", title: "收益论证", detail: "整理可行性与正向论据", icon: Sparkles },
  { key: "fact_check", title: "事实核查", detail: "检索来源并绑定证据", icon: ShieldCheck },
  { key: "risk_argument", title: "风险研判", detail: "识别缺陷、风险与落地约束", icon: AlertTriangle },
  { key: "summary_report", title: "汇总评审", detail: "生成结构化 Markdown 报告", icon: BookOpen },
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

const sampleMaterials = [
  { id: "knowledge-base", title: "企业知识库升级", category: "技术方案", topic: "评估企业知识库升级方案的收益、风险与实施约束", summary: "适合演示检索增强、权限治理与迁移成本的交叉评审。", material: "目标：统一 12 个业务知识源；范围：RAG 检索、权限继承、历史文档迁移；约束：首期预算 80 万元，要求 3 个月内上线。", tags: ["知识库", "RAG", "迁移"] },
  { id: "customer-service", title: "客服自动化项目", category: "立项材料", topic: "评估客服自动化项目的投入产出、服务质量风险与上线条件", summary: "覆盖人机协同、合规审查和服务指标设计。", material: "目标：自动处理 60% 常见咨询；范围：智能问答、工单分流、人工接管；约束：涉及客户隐私数据，需保留全量审计记录。", tags: ["客服", "自动化", "合规"] },
  { id: "data-platform", title: "数据平台整合", category: "调研主题", topic: "评估多业务线数据平台整合的收益、技术风险与组织约束", summary: "适合测试多来源证据、数据治理和组织协作问题。", material: "目标：整合销售、供应链与财务数据；范围：统一指标、数据目录、权限模型；约束：现有系统不能停机，需分阶段迁移并保持口径兼容。", tags: ["数据治理", "平台", "组织"] },
];

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

function estimateReviewMinutes(roundCount: number) {
  // Parse + four agent passes per round + report synthesis, rounded to a
  // whole minute so the estimate is understandable before a task starts.
  return Math.max(1, Math.ceil(2.5 + Math.max(1, roundCount) * 4.2));
}

export default function HomePage() {
  const { user, loading, logout } = useAuth();
  const [view, setView] = useState<ViewKey>("review");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [organization, setOrganization] = useState("");
  const [reviews, setReviews] = useState<ReviewSummary[]>([]);
  const [selected, setSelected] = useState<ReviewDetail | null>(null);
  const [topic, setTopic] = useState("");
  const [rounds, setRounds] = useState(() => {
    if (typeof window === "undefined") return 3;
    const saved = Number(window.localStorage.getItem("review.defaultRounds"));
    return saved >= 1 && saved <= 5 ? saved : 3;
  });
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [events, setEvents] = useState<ReviewEvent[]>([]);
  const [streamContent, setStreamContent] = useState<Record<string, string>>({});
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteMessage, setInviteMessage] = useState("");
  const [humanBusy, setHumanBusy] = useState(false);
  const [autoExpandEvidence, setAutoExpandEvidence] = useState(() => typeof window !== "undefined" && window.localStorage.getItem("review.autoExpandEvidence") === "true");
  const [preferenceMessage, setPreferenceMessage] = useState("");
  const selectedRef = useRef<ReviewDetail | null>(null);
  const orgRef = useRef<string | undefined>(undefined);
  const activeOrg = useMemo(() => user?.organizations.find((item) => item.id === organization) || user?.organizations[0], [organization, user]);

  useEffect(() => { selectedRef.current = selected; }, [selected]);
  useEffect(() => { orgRef.current = activeOrg?.id; }, [activeOrg?.id]);
  useEffect(() => { if (activeOrg) api.reviews.list(activeOrg.id).then(setReviews).catch((err) => setError(err.message)); }, [activeOrg]);

  const onEvent = useCallback((event: ReviewEvent) => {
    setEvents((previous) => [...previous.filter((item) => item.sequence !== event.sequence), event]);
    if (event.type === "agent_chunk" && typeof event.agent === "string" && typeof event.content === "string") setStreamContent((previous) => ({ ...previous, [event.agent as string]: `${previous[event.agent as string] || ""}${event.content as string}` }));
    if (event.type === "agent_result" && typeof event.agent === "string") setStreamContent((previous) => { const next = { ...previous }; delete next[event.agent as string]; return next; });
    if (event.type === "error") {
      const message = typeof event.message === "string" && event.message.trim() ? event.message : "评审执行失败，请查看任务详情后重试。";
      setError(message);
    }
    const current = selectedRef.current; const orgId = orgRef.current;
    if (current && ["done", "error", "report_ready", "session_status", "agent_result"].includes(event.type)) api.reviews.get(current.id, orgId).then((detail) => { selectedRef.current = detail; setSelected(detail); }).catch(() => undefined);
    if (event.type === "evidence_upsert" && current) api.reviews.evidence(current.id, orgId).then(setEvidence).catch(() => undefined);
  }, []);
  const { connect, connected } = useReviewStream(selected?.id || null, onEvent);

  function showView(nextView: ViewKey) { setView(nextView); setMobileMenuOpen(false); setError(""); }
  function loadSample(sample: (typeof sampleMaterials)[number]) { setTopic(sample.topic); setNotice(`已载入示例材料：${sample.title}`); setView("review"); setMobileMenuOpen(false); window.setTimeout(() => setNotice(""), 3200); }

  async function createReview() {
    if (!user) { setError("请先登录，再启动评审"); return; }
    if (!activeOrg || (!topic.trim() && files.length === 0)) { setError("请输入调研主题或上传至少一个文档"); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const review = await api.reviews.create({ organization_id: activeOrg.id, topic: topic.trim() || undefined, max_round: rounds });
      for (const file of files) await api.reviews.upload(review.id, file, activeOrg.id);
      const detail = await api.reviews.get(review.id, activeOrg.id); setSelected(detail); selectedRef.current = detail; setStreamContent({});
      setReviews((previous) => [review, ...previous]); setTopic(""); setFiles([]); await api.reviews.start(review.id, activeOrg.id); connect(review.id);
    } catch (err) { setError(err instanceof Error ? err.message : "创建评审失败"); } finally { setBusy(false); }
  }

  async function selectReview(id: string) {
    if (!activeOrg) return;
    try { const detail = await api.reviews.get(id, activeOrg.id); setSelected(detail); selectedRef.current = detail; setEvents([]); setStreamContent({}); setEvidence(await api.reviews.evidence(id, activeOrg.id)); if (["running", "queued", "interrupted"].includes(detail.status)) connect(id); }
    catch (err) { setError(err instanceof Error ? err.message : "加载评审失败"); }
  }

  async function downloadReport() {
    if (!selected) return; const response = await fetch(api.reviews.downloadUrl(selected.id), { credentials: "include" });
    if (!response.ok) { setError(response.status === 401 ? "登录已过期，请重新登录" : "报告下载失败"); return; }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `review-${selected.id.slice(0, 8)}.md`; anchor.click(); URL.revokeObjectURL(url);
  }

  async function humanReview(approved: boolean) {
    if (!selected || !activeOrg) return; setHumanBusy(true);
    try { await api.reviews.humanReview(selected.id, approved, undefined, activeOrg.id); const detail = await api.reviews.get(selected.id, activeOrg.id); setSelected(detail); selectedRef.current = detail; if (approved) connect(selected.id); }
    catch (err) { setError(err instanceof Error ? err.message : "人工复核提交失败"); } finally { setHumanBusy(false); }
  }

  async function deleteReview() {
    if (!selected || !activeOrg || !window.confirm("确定删除这个评审任务吗？此操作不可撤销。")) return;
    try { await api.reviews.delete(selected.id, activeOrg.id); setReviews((previous) => previous.filter((item) => item.id !== selected.id)); setSelected(null); selectedRef.current = null; setEvidence([]); setEvents([]); }
    catch (err) { setError(err instanceof Error ? err.message : "删除评审失败"); }
  }

  async function inviteMember() {
    if (!activeOrg || !inviteEmail.trim()) return;
    try { await api.organizations.invite(activeOrg.id, inviteEmail.trim()); setInviteMessage("邀请已发送"); setInviteEmail(""); }
    catch (err) { setInviteMessage(err instanceof Error ? err.message : "邀请失败"); }
  }

  function savePreferences() {
    window.localStorage.setItem("review.defaultRounds", String(rounds));
    window.localStorage.setItem("review.autoExpandEvidence", String(autoExpandEvidence));
    setPreferenceMessage("偏好已保存到当前浏览器");
    window.setTimeout(() => setPreferenceMessage(""), 2600);
  }

  function addFiles(event: ChangeEvent<HTMLInputElement>) {
    if (!user) { setError("登录后才能上传评审材料"); event.target.value = ""; return; }
    const next = Array.from(event.target.files || []); const invalidType = next.find((file) => !/\.(pdf|docx)$/i.test(file.name)); const oversized = next.find((file) => file.size > 20 * 1024 * 1024);
    if (invalidType) { setError(`不支持文件格式：${invalidType.name}`); return; } if (oversized) { setError(`文件超过 20 MB：${oversized.name}`); return; } if (files.length + next.length > 5) { setError("每个评审最多上传 5 个文件"); return; }
    setError(""); setFiles((previous) => [...previous, ...next]); event.target.value = "";
  }

  if (loading) return <div className="loading-screen"><div className="loading-orbit" /><span>正在加载工作区</span></div>;

  const navItems: { key: ViewKey; label: string; icon: typeof LayoutDashboard; hint: string }[] = [
    { key: "review", label: "评审工作台", icon: LayoutDashboard, hint: "创建与跟踪评审" },
    { key: "orchestration", label: "Agent 编排", icon: Workflow, hint: "查看处理流程" },
    { key: "evidence", label: "证据库", icon: Database, hint: "检索来源与论据" },
    { key: "settings", label: "系统设置", icon: Settings2, hint: "组织与偏好设置" },
  ];

  return <div className="review-shell">
    {mobileMenuOpen && <button className="drawer-scrim" aria-label="关闭导航" onClick={() => setMobileMenuOpen(false)} />}
    <aside className={`review-sidebar ${mobileMenuOpen ? "open" : ""}`}>
      <div className="sidebar-brand"><div className="brand"><span className="brand-mark">R</span><span><strong>交叉评审</strong><small>Review Mesh</small></span></div><button className="icon-button mobile-close" aria-label="关闭导航" onClick={() => setMobileMenuOpen(false)}><X size={18} /></button></div>
      <div className="workspace-switcher"><span className="eyebrow">组织工作区</span>{user ? <select className="select" value={activeOrg?.id || ""} onChange={(event) => setOrganization(event.target.value)}>{user.organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}</select> : <div className="preview-workspace"><span>演示工作区</span><small>登录后加载组织数据</small></div>}</div>
      <nav className="side-nav" aria-label="工作区导航">{navItems.map((item) => { const Icon = item.icon; return <button key={item.key} className={`nav-item ${view === item.key ? "active" : ""}`} onClick={() => showView(item.key)}><Icon size={17} /><span><strong>{item.label}</strong><small>{item.hint}</small></span></button>; })}</nav>
      <div className="sidebar-history"><div className="section-heading"><span>最近评审</span><span className="count-badge">{reviews.length}</span></div>{reviews.length === 0 ? <div className="history-empty">还没有评审任务</div> : reviews.slice(0, 8).map((item) => <button key={item.id} className={`history-item ${selected?.id === item.id ? "active" : ""}`} onClick={() => { void selectReview(item.id); showView("review"); }}><strong title={item.topic || "未命名文档评审"}>{item.topic || "未命名文档评审"}</strong><span>{statusLabels[item.status] || "草稿"}<i />{formatDate(item.created_at)}</span></button>)}</div>
      <div className="sidebar-footer">{user ? <><div className="profile-row"><span className="avatar">{(user.display_name || user.email).slice(0, 1).toUpperCase()}</span><span className="profile-copy"><strong>{user.display_name || "评审成员"}</strong><small>{user.email}</small></span></div><button className="logout-button" onClick={logout}><LogOut size={15} />退出登录</button></> : <Link className="login-sidebar-link" href="/login">登录后开始评审 <ExternalLink size={14} /></Link>}</div>
    </aside>
    <main className="review-main">
      <header className="topbar"><div className="topbar-left"><button className="icon-button menu-trigger" aria-label="打开导航" onClick={() => setMobileMenuOpen(true)}><Menu size={19} /></button><div className="breadcrumbs"><span>工作区</span><b>/</b><strong>{navItems.find((item) => item.key === view)?.label}</strong></div></div><div className="topbar-actions"><span className={`connection-state ${connected ? "live" : ""}`}><i />{connected ? "实时同步" : user ? "系统正常" : "演示模式"}</span><button className="icon-button" aria-label="帮助"><CircleHelp size={18} /></button>{user ? <button className="new-review-button" onClick={() => { showView("review"); setSelected(null); }}><Plus size={17} />新建评审</button> : <Link className="login-top-button" href="/login">登录使用</Link>}</div></header>
      {view === "review" && <div className="page-content review-view">
        <section className="hero-strip"><div><span className="eyebrow accent-eyebrow">REVIEW WORKSPACE</span><h1>{selected?.topic || "方案交叉评审工作台"}</h1><p>{selected ? `${activeOrg?.name} · ${statusLabels[selected.status] || selected.status}` : "让多个 Agent 从收益、风险与事实证据三个角度交叉审阅方案。"}</p></div><div className="hero-metrics"><div><strong>{reviews.length}</strong><span>评审任务</span></div><div><strong>{evidence.length}</strong><span>证据条目</span></div><div><strong>{selected?.max_round || rounds}</strong><span>当前轮次</span></div><div><strong>{estimateReviewMinutes(selected?.max_round || rounds)}</strong><span>预计分钟</span></div></div></section>
        {selected && ["queued", "running"].includes(selected.status) && <div className="progress-banner"><Timer size={16} /><span>本次评审预计约 <strong>{estimateReviewMinutes(selected.max_round)} 分钟</strong>，当前正在处理“{labels[selected.current_stage] || selected.current_stage}”。结果会持续写入任务记录，页面断线后可自动恢复。</span></div>}
        {selected?.error_message && <div className="error-banner"><AlertTriangle size={16} />{selected.error_message}</div>}
        <section className="glass-panel composer-panel"><div className="panel-heading"><div><span className="section-kicker"><Sparkles size={14} />开始一次新评审</span><h2>输入评审材料</h2><p>输入主题，或上传方案与立项文档，Agent 会自动建立证据链。</p></div><div className="panel-tools"><span className="panel-help"><CircleHelp size={16} />支持 PDF / DOCX</span><span className="time-estimate"><Clock3 size={14} />预计约 {estimateReviewMinutes(rounds)} 分钟</span></div></div><div className="composer-grid"><div className="topic-field field"><label htmlFor="topic">调研主题</label><textarea id="topic" className="textarea" placeholder="例如：评估企业知识库升级方案的收益、风险与实施约束" value={topic} onChange={(event) => setTopic(event.target.value)} /><div className="field-foot"><span>{topic.length}/500</span><span>建议描述目标、范围和关键约束</span></div></div><div className="composer-side"><div className="field"><label htmlFor="rounds">评审轮次</label><div className="select-wrap"><select id="rounds" className="select" value={rounds} onChange={(event) => setRounds(Number(event.target.value))}>{[1, 2, 3, 4, 5].map((number) => <option key={number} value={number}>{number} 轮 · 约 {estimateReviewMinutes(number)} 分钟</option>)}</select></div></div><label className="dropzone" onClick={(event) => { if (!user) { event.preventDefault(); setError("登录后才能上传评审材料"); } }}><Upload size={20} /><strong>添加 PDF / DOCX</strong><span>单任务最多 5 个文件，每个不超过 20 MB</span><input type="file" accept=".pdf,.docx" multiple onChange={addFiles} /></label><button className="primary start-button" disabled={busy} onClick={() => void createReview()}><Play size={16} />{busy ? "准备评审中" : "启动评审"}</button></div></div>{files.length > 0 && <div className="file-list">{files.map((file, index) => <div className="file-row" key={`${file.name}-${index}`}><span><FileText size={14} />{file.name}</span><button className="text-button" onClick={() => setFiles(files.filter((_, itemIndex) => itemIndex !== index))}>移除</button></div>)}</div>}</section>
        <section className="sample-section"><div className="section-heading"><div><span className="section-kicker"><BookOpen size={14} />快速开始</span><h2>示例评审材料</h2></div><span className="muted-copy">选择一个示例即可载入主题</span></div><div className="sample-grid">{sampleMaterials.map((sample) => <article className="sample-card" key={sample.id}><div className="sample-card-top"><span className="sample-icon"><FileText size={17} /></span><span className="sample-category">{sample.category}</span></div><h3>{sample.title}</h3><p>{sample.summary}</p><div className="sample-material">{sample.material}</div><div className="tag-row">{sample.tags.map((tag) => <span key={tag}>{tag}</span>)}</div><button className="sample-action" onClick={() => loadSample(sample)}>使用此示例 <ExternalLink size={14} /></button></article>)}</div></section>
        <section className="glass-panel activity-panel"><div className="panel-heading compact"><div><span className="section-kicker"><Workflow size={14} />实时活动</span><h2>Agent 工作流</h2><p>每条输出会进入证据池并绑定检索来源。</p></div><span className="round-indicator"><Clock3 size={14} />{selected ? `${selected.current_round} / ${selected.max_round} 轮` : "等待启动"}</span></div><div className="agent-list">{stageCards.map((stage, index) => { const latest = [...(selected?.outputs || [])].reverse().find((output) => output.agent_role === stage.key); const activeRound = latest?.round_num ?? selected?.current_round ?? 0; const lastStart = [...events].reverse().find((event) => event.type === "agent_start" && event.agent === stage.key && (Number(event.round || 0) === activeRound || stage.key === "document_parse")); const lastResult = [...events].reverse().find((event) => (event.type === "agent_result" && event.agent === stage.key) || (stage.key === "fact_check" && event.type === "evidence_upsert" && event.agent === "fact_check" && event.verdict)); const terminal = selected?.status === "completed" || selected?.status === "failed" || selected?.status === "needs_revision"; const hasResult = Boolean(latest || (terminal && stage.key === "fact_check" && evidence.length > 0) || (terminal && stage.key === "summary_report" && selected?.report_markdown)); const live = !terminal && Boolean(lastStart && (!lastResult || lastStart.sequence > lastResult.sequence)); const Icon = stage.icon; return <article className={`agent-card ${live ? "live" : ""}`} key={stage.key}><div className="agent-index">{String(index + 1).padStart(2, "0")}</div><div className="agent-type-icon"><Icon size={17} /></div><div className="agent-copy"><h3>{labels[stage.key]}</h3><p>{latest?.content_markdown || streamContent[stage.key] || (live ? "正在处理当前材料..." : stage.detail)}</p></div><div className={`agent-status ${live ? "processing" : hasResult ? "complete" : "waiting"}`}>{live ? "处理中" : hasResult ? "已完成" : "等待中"}</div></article>; })}</div></section>
        <div className="two-column"><section className="glass-panel evidence-panel"><div className="panel-heading compact"><div><span className="section-kicker"><ShieldCheck size={14} />可追溯证据</span><h2>证据池</h2><p>每条论据的核查状态与来源链接。</p></div><button className="ghost-link" onClick={() => showView("evidence")}>查看全部 <ExternalLink size={14} /></button></div>{evidence.length === 0 ? <div className="empty compact-empty"><Database size={28} /><strong>等待证据进入证据库</strong><span>启动评审后，事实核查 Agent 会在这里记录来源。</span></div> : <div className="evidence-preview">{evidence.slice(0, 4).map((item) => <EvidenceRow item={item} defaultExpanded={autoExpandEvidence} key={item.id} />)}</div>}</section><section className="glass-panel report-panel"><div className="panel-heading compact"><div><span className="section-kicker"><BookOpen size={14} />结构化输出</span><h2>评审报告</h2><p>完成后生成五段式 Markdown 报告。</p></div><div className="panel-actions">{selected?.report_markdown && <button className="icon-button" aria-label="下载 Markdown" title="下载 Markdown" onClick={() => void downloadReport()}><Download size={17} /></button>}{user && selected && (activeOrg?.role === "owner" || selected.creator_id === user.id) && <button className="icon-button danger-action" aria-label="删除评审" title="删除评审" onClick={() => void deleteReview()}><Trash2 size={17} /></button>}</div></div>{selected?.status === "awaiting_human" && <div className="human-review"><span>报告生成前需要人工确认</span><div><button className="secondary" disabled={humanBusy} onClick={() => void humanReview(false)}>暂不通过</button><button className="primary" disabled={humanBusy} onClick={() => void humanReview(true)}>确认生成报告</button></div></div>}{selected?.report_markdown ? <div className="report report-preview">{selected.report_markdown}</div> : <div className="empty compact-empty"><BookOpen size={28} /><strong>报告将在汇总评审完成后展示</strong><span>你可以先选择一个示例主题开始体验。</span></div>}</section></div>
        {error && !selected?.error_message && <div className="error-banner"><AlertTriangle size={16} />{error}</div>}{notice && <div className="notice-banner"><CheckCircle2 size={16} />{notice}</div>}
      </div>}
      {view === "orchestration" && <OrchestrationView selected={selected} connected={connected} rounds={rounds} />}
      {view === "evidence" && <EvidenceView evidence={evidence} defaultExpanded={autoExpandEvidence} onBack={() => showView("review")} />}
      {view === "settings" && <SettingsView authenticated={Boolean(user)} activeOrg={activeOrg} rounds={rounds} setRounds={setRounds} autoExpandEvidence={autoExpandEvidence} setAutoExpandEvidence={setAutoExpandEvidence} inviteEmail={inviteEmail} setInviteEmail={setInviteEmail} inviteMessage={inviteMessage} preferenceMessage={preferenceMessage} onSavePreferences={savePreferences} onInvite={() => void inviteMember()} />}
    </main>
  </div>;
}

function EvidenceRow({ item, defaultExpanded = false }: { item: EvidenceItem; defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const verdictLabel = item.verdict === "verified" ? "已核实" : item.verdict === "contradicted" ? "有冲突" : "待确认";
  return <article className={`evidence-row ${expanded ? "expanded" : ""}`}><div className={`verdict-dot ${item.verdict}`} /><div className="evidence-copy"><strong>{item.claim_text}</strong><span>{item.rationale}</span><button className="evidence-toggle" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>{expanded ? "收起来源" : `查看来源${item.sources.length ? ` · ${item.sources.length}` : ""}`} {expanded ? <X size={12} /> : <ExternalLink size={12} />}</button>{expanded && <div className="source-links">{item.sources.length ? item.sources.map((source) => <a key={source.id} href={source.url} target="_blank" rel="noreferrer">{source.title}<ExternalLink size={11} /></a>) : <span className="no-source">暂无可靠来源，已保留为待确认。</span>}</div>}</div><span className={`verdict ${item.verdict}`}>{verdictLabel}</span></article>;
}

function OrchestrationView({ selected, connected, rounds }: { selected: ReviewDetail | null; connected: boolean; rounds: number }) {
  const activeRounds = selected?.max_round || rounds;
  return <div className="page-content secondary-view"><section className="hero-strip secondary-hero"><div><span className="eyebrow accent-eyebrow">AGENT ORCHESTRATION</span><h1>Agent 编排</h1><p>查看评审任务如何在五个固定角色之间流转，输出始终保持可追溯。</p></div><span className={`large-status ${connected ? "live" : ""}`}><i />{connected ? "实时运行中" : "编排器就绪"}</span></section><section className="glass-panel workflow-panel"><div className="panel-heading"><div><span className="section-kicker"><Workflow size={14} />处理路径</span><h2>方案交叉评审流程</h2><p>每轮固定执行收益论证、事实核查、风险研判、事实核查。</p></div><span className="round-indicator"><SlidersHorizontal size={14} />{activeRounds} 轮上限 · 预计 {estimateReviewMinutes(activeRounds)} 分钟</span></div><div className="workflow-track">{stageCards.map((stage, index) => { const Icon = stage.icon; const done = Boolean(selected?.outputs?.some((output) => output.agent_role === stage.key)); return <div className="workflow-node" key={stage.key}><div className={`workflow-node-icon ${done ? "done" : ""}`}><Icon size={20} /></div><strong>{stage.title}</strong><span>{stage.detail}</span>{index < stageCards.length - 1 && <div className="workflow-line" />}</div>; })}</div></section><div className="orchestration-grid"><section className="glass-panel info-panel"><span className="section-kicker"><Gauge size={14} />执行策略</span><h2>固定顺序，逐轮核查</h2><div className="strategy-list"><div><strong>轮次上限</strong><span>{activeRounds} 轮</span></div><div><strong>核查策略</strong><span>每条论据单独检索</span></div><div><strong>失败处理</strong><span>结构化重试 1 次</span></div><div><strong>估算耗时</strong><span>约 {estimateReviewMinutes(activeRounds)} 分钟</span></div></div></section><section className="glass-panel info-panel"><span className="section-kicker"><RefreshCw size={14} />运行检查</span><h2>服务状态</h2><div className="check-list"><div><span><i className="check-dot ok" />模型客户端</span><strong>可用</strong></div><div><span><i className={`check-dot ${connected ? "ok" : "idle"}`} />SSE 实时推送</span><strong>{connected ? "已连接" : "等待任务"}</strong></div><div><span><i className="check-dot ok" />证据持久化</span><strong>已启用</strong></div><div><span><i className="check-dot ok" />组织隔离</span><strong>已启用</strong></div></div></section></div><section className="glass-panel agent-config-panel"><div className="panel-heading compact"><div><span className="section-kicker"><SlidersHorizontal size={14} />节点详情</span><h2>五个 Agent 的输入与输出</h2><p>每个节点都有明确的失败边界，便于定位长时间无输出的问题。</p></div></div><div className="agent-config-grid">{stageCards.map((stage) => <article key={stage.key}><div className="agent-config-title"><stage.icon size={16} /><strong>{stage.title}</strong></div><span>输入：{stage.key === "document_parse" ? "主题或文档" : "上一阶段结构化结果"}</span><span>输出：{stage.key === "fact_check" ? "证据与核查结论" : stage.key === "summary_report" ? "Markdown 报告" : "摘要与论据"}</span></article>)}</div></section></div>;
}

function EvidenceView({ evidence, defaultExpanded, onBack }: { evidence: EvidenceItem[]; defaultExpanded: boolean; onBack: () => void }) {
  return <div className="page-content secondary-view"><section className="hero-strip secondary-hero"><div><span className="eyebrow accent-eyebrow">EVIDENCE LIBRARY</span><h1>证据库</h1><p>集中查看所有已核查论据、结论和外部来源。</p></div><div className="evidence-total"><strong>{evidence.length}</strong><span>条证据</span></div></section><section className="glass-panel library-panel"><div className="library-toolbar"><div className="search-field"><Search size={16} /><input aria-label="搜索证据" placeholder="搜索论据或来源标题" /></div><span className="muted-copy">仅展示当前选中评审的证据</span></div>{evidence.length === 0 ? <div className="empty library-empty"><Database size={34} /><strong>证据库还是空的</strong><span>选择一个评审并启动事实核查后，证据会自动沉淀到这里。</span><button className="secondary" onClick={onBack}>返回工作台</button></div> : <div className="library-list">{evidence.map((item) => <EvidenceRow item={item} defaultExpanded={defaultExpanded} key={item.id} />)}</div>}</section></div>;
}

function SettingsView({ authenticated, activeOrg, rounds, setRounds, autoExpandEvidence, setAutoExpandEvidence, inviteEmail, setInviteEmail, inviteMessage, preferenceMessage, onSavePreferences, onInvite }: { authenticated: boolean; activeOrg?: { id: string; name: string; role: string }; rounds: number; setRounds: (value: number) => void; autoExpandEvidence: boolean; setAutoExpandEvidence: (value: boolean) => void; inviteEmail: string; setInviteEmail: (value: string) => void; inviteMessage: string; preferenceMessage: string; onSavePreferences: () => void; onInvite: () => void }) {
  return <div className="page-content secondary-view"><section className="hero-strip secondary-hero"><div><span className="eyebrow accent-eyebrow">WORKSPACE SETTINGS</span><h1>系统设置</h1><p>管理组织成员、评审偏好与证据展示方式。</p></div></section><div className="settings-grid"><section className="glass-panel settings-panel"><div className="panel-heading compact"><div><span className="section-kicker"><Settings2 size={14} />组织信息</span><h2>{activeOrg?.name || "演示工作区"}</h2><p>{authenticated ? `当前成员权限：${activeOrg?.role === "owner" ? "Owner" : "Member"}` : "演示模式仅展示工作区能力"}</p></div></div><div className="setting-list"><div><span>证据来源</span><strong>联网检索工具</strong></div><div><span>文件存储</span><strong>Supabase 私有存储</strong></div><div><span>访问范围</span><strong>组织成员可见</strong></div><div><span>安全策略</span><strong><LockKeyhole size={13} /> JWT + 组织隔离</strong></div></div></section><section className="glass-panel settings-panel"><div className="panel-heading compact"><div><span className="section-kicker"><SlidersHorizontal size={14} />评审偏好</span><h2>调整工作方式</h2><p>偏好保存于当前浏览器，新建评审时自动使用。</p></div></div><div className="preference-form"><label className="setting-control"><span>默认评审轮次</span><select className="select" value={rounds} onChange={(event) => setRounds(Number(event.target.value))}>{[1, 2, 3, 4, 5].map((number) => <option key={number} value={number}>{number} 轮 · 约 {estimateReviewMinutes(number)} 分钟</option>)}</select></label><label className="toggle-row"><input type="checkbox" checked={autoExpandEvidence} onChange={(event) => setAutoExpandEvidence(event.target.checked)} /><span><strong>自动展开证据来源</strong><small>进入证据库时直接展示来源链接</small></span></label><button className="primary" onClick={onSavePreferences}><Save size={15} />保存偏好</button>{preferenceMessage && <div className="inline-message">{preferenceMessage}</div>}</div></section><section className="glass-panel settings-panel"><div className="panel-heading compact"><div><span className="section-kicker"><Users size={14} />团队成员</span><h2>邀请成员</h2><p>Owner 可以邀请组织成员加入评审空间。</p></div></div>{authenticated ? <div className="invite-form"><label className="field"><span>同事邮箱</span><input className="input" type="email" placeholder="name@company.com" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} /></label><button className="primary" onClick={onInvite}>发送邀请</button>{inviteMessage && <div className="inline-message">{inviteMessage}</div>}</div> : <div className="login-required"><strong>登录后管理组织成员</strong><span>演示模式可以浏览界面，组织与评审数据需要登录后访问。</span><Link className="primary" href="/login">登录使用</Link></div>}</section><section className="glass-panel settings-panel"><div className="panel-heading compact"><div><span className="section-kicker"><ShieldCheck size={14} />数据与安全</span><h2>评审数据保护</h2><p>数据访问和文件处理遵循组织边界。</p></div></div><div className="setting-list"><div><span>原件存储</span><strong>私有桶</strong></div><div><span>外部链接</span><strong>新窗口打开</strong></div><div><span>删除权限</span><strong>创建者 / Owner</strong></div></div></section></div></div>;
}
