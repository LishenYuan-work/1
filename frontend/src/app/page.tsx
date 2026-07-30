"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { debates, type DebateSummary } from "@/lib/api";
import { MessageCircle, Clock, Users } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  pending: "等待中", running: "进行中", completed: "已完成", failed: "失败",
};
const STATUS_COLORS: Record<string, string> = {
  pending: "#f59e0b", running: "#10b981", completed: "#6366f1", failed: "#ef4444",
};

export default function HomePage() {
  const [list, setList] = useState<DebateSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    debates.list({ limit: 30 }).then(setList).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p style={{ color: "var(--sub)", textAlign: "center", padding: "4rem 0" }}>加载中…</p>;
  }

  if (list.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "4rem 0", color: "var(--sub)" }}>
        <MessageCircle size={48} className="mx-auto mb-3 opacity-30" />
        <p className="font-semibold text-lg">还没有公开辩论</p>
        <p className="text-sm mt-1">
          <Link href="/create" style={{ color: "var(--accent)" }}>创建第一场辩论</Link>
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-lg font-bold mb-4">发现辩论</h1>
      <div className="grid gap-3">
        {list.map((d) => (
          <Link key={d.id} href={`/debate?id=${d.id}`} className="no-underline"
            style={{ color: "var(--text)" }}>
            <div className="p-4 rounded-xl border transition-shadow hover:shadow-md"
              style={{ background: "var(--card)", borderColor: "var(--border)" }}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-base m-0 mb-1 truncate">{d.topic}</h3>
                  <div className="flex items-center gap-3 text-xs" style={{ color: "var(--sub)" }}>
                    <span className="flex items-center gap-1"><Users size={12} />{d.agents.length} 位辩手</span>
                    <span className="flex items-center gap-1"><MessageCircle size={12} />{d.message_count} 条发言</span>
                    <span className="flex items-center gap-1"><Clock size={12} />{d.rounds} 轮</span>
                    {d.creator_name && <span>by {d.creator_name}</span>}
                  </div>
                </div>
                <span className="text-xs px-2 py-1 rounded-full font-semibold ml-2"
                  style={{ color: STATUS_COLORS[d.status], background: STATUS_COLORS[d.status] + "18" }}>
                  {STATUS_LABELS[d.status] || d.status}
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
