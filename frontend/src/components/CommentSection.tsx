"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { comments, type CommentItem } from "@/lib/api";
import { MessageSquare, Send, Trash2, ChevronRight } from "lucide-react";

export default function CommentSection({ debateId, done }: { debateId: string; done: boolean }) {
  const { user } = useAuth();
  const [list, setList] = useState<CommentItem[]>([]);
  const [content, setContent] = useState("");
  const [replyTo, setReplyTo] = useState<number | null>(null);
  const [replyContent, setReplyContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      const data = await comments.list(debateId);
      setList(data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (done) load(); }, [debateId, done]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!content.trim() || !user) return;
    setSubmitting(true); setError("");
    try {
      const c = await comments.create(debateId, { content: content.trim() });
      setList((prev) => [...prev, c]);
      setContent("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "发表失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReply(parentId: number) {
    if (!replyContent.trim() || !user) return;
    setSubmitting(true);
    try {
      const c = await comments.create(debateId, { content: replyContent.trim(), parent_id: parentId });
      setList((prev) => prev.map((item) => {
        if (item.id === parentId) {
          return { ...item, replies: [...item.replies, c] };
        }
        return item;
      }));
      setReplyTo(null);
      setReplyContent("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "回复失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(commentId: number) {
    try {
      await comments.delete(debateId, commentId);
      setList((prev) => prev.filter((c) => c.id !== commentId));
    } catch {
      // silently fail
    }
  }

  if (!done) return null;

  return (
    <div className="mt-8 pt-6" style={{ borderTop: "2px solid var(--border)" }}>
      <h3 className="flex items-center gap-2 text-base font-bold mb-4">
        <MessageSquare size={18} /> 评论 ({list.length})
      </h3>

      {/* 发表评论 */}
      {user ? (
        <form onSubmit={handleSubmit} className="flex gap-2 mb-6">
          <input type="text" value={content} onChange={(e) => setContent(e.target.value)}
            placeholder="发表你的看法…" required minLength={1}
            className="flex-1 px-3 py-2 rounded-lg border text-sm"
            style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }} />
          <button type="submit" disabled={submitting || !content.trim()}
            className="px-4 py-2 rounded-lg text-white border-0 cursor-pointer disabled:opacity-50 text-sm"
            style={{ background: "var(--accent)" }}>
            <Send size={14} />
          </button>
        </form>
      ) : (
        <p className="text-sm mb-4" style={{ color: "var(--sub)" }}>请登录后发表评论</p>
      )}

      {error && <p className="text-red-500 text-xs mb-2">{error}</p>}

      {/* 评论列表 */}
      {loading ? (
        <p className="text-sm" style={{ color: "var(--sub)" }}>加载中…</p>
      ) : list.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--sub)" }}>暂无评论，来说两句吧</p>
      ) : (
        <div className="flex flex-col gap-3">
          {list.map((c) => (
            <CommentNode key={c.id} comment={c} depth={0}
              replyTo={replyTo} replyContent={replyContent}
              setReplyTo={setReplyTo} setReplyContent={setReplyContent}
              onReply={handleReply} onDelete={handleDelete}
              currentUserId={user?.id} />
          ))}
        </div>
      )}
    </div>
  );
}

function CommentNode({
  comment, depth, replyTo, replyContent, setReplyTo, setReplyContent, onReply, onDelete, currentUserId,
}: {
  comment: CommentItem; depth: number;
  replyTo: number | null; replyContent: string;
  setReplyTo: (id: number | null) => void; setReplyContent: (v: string) => void;
  onReply: (id: number) => Promise<void>; onDelete: (id: number) => Promise<void>;
  currentUserId?: string | null;
}) {
  const isOwner = currentUserId && currentUserId === comment.user_id;

  return (
    <div style={{ marginLeft: depth > 0 ? Math.min(depth * 20, 40) : 0 }}>
      <div className="p-3 rounded-lg" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold">{comment.username || "匿名"}</span>
            <span style={{ color: "var(--sub)" }}>{comment.created_at?.slice(0, 16).replace("T", " ")}</span>
          </div>
          {isOwner && (
            <button onClick={() => onDelete(comment.id)}
              className="bg-transparent border-0 cursor-pointer" style={{ color: "var(--sub)" }}>
              <Trash2 size={12} />
            </button>
          )}
        </div>
        <p className="text-sm m-0 leading-relaxed">{comment.content}</p>

        {/* 回复按钮 */}
        <button onClick={() => setReplyTo(replyTo === comment.id ? null : comment.id)}
          className="text-xs bg-transparent border-0 cursor-pointer mt-1"
          style={{ color: "var(--accent)" }}>
          回复
        </button>

        {/* 回复输入框 */}
        {replyTo === comment.id && (
          <div className="flex gap-2 mt-2">
            <input type="text" value={replyContent} onChange={(e) => setReplyContent(e.target.value)}
              placeholder={`回复 ${comment.username}…`}
              onKeyDown={(e) => e.key === "Enter" && onReply(comment.id)}
              className="flex-1 px-2 py-1 rounded border text-xs"
              style={{ borderColor: "var(--border)", background: "var(--bg)", color: "var(--text)" }} />
            <button onClick={() => onReply(comment.id)}
              className="px-2 py-1 rounded text-white border-0 cursor-pointer text-xs"
              style={{ background: "var(--accent)" }}>
              <Send size={10} />
            </button>
          </div>
        )}
      </div>

      {/* 嵌套回复 */}
      {comment.replies.length > 0 && (
        <div className="mt-1">
          {comment.replies.map((r) => (
            <CommentNode key={r.id} comment={r} depth={depth + 1}
              replyTo={replyTo} replyContent={replyContent}
              setReplyTo={setReplyTo} setReplyContent={setReplyContent}
              onReply={onReply} onDelete={onDelete}
              currentUserId={currentUserId} />
          ))}
        </div>
      )}
    </div>
  );
}
