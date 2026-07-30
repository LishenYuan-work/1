"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { debates, type DebateSummary } from "@/lib/api";
import { MessageCircle, Clock, Users, Loader2 } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  pending: "等待中", running: "进行中", completed: "已完成", failed: "失败",
};
const STATUS_COLORS: Record<string, string> = {
  pending: "#f59e0b", running: "#10b981", completed: "#6366f1", failed: "#ef4444",
};

export default function DashboardPage() {
  const { user } = useAuth();
  const [list, setList] = useState<DebateSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user) debates.myList().then(setList).catch(console.error).finally(() => setLoading(false));
  }, [user]);

  if (!user) {
    return (
      <div className="text-center py-20" style={{ color: "var(--sub)" }}>
        <p className="font-semibold">请先登录</p>
        <Link href="/login" style={{ color: "var(--accent)" }}>前往登录</Link>
      </div>
    );
  }

  return (
    <div className="w-full max-w-3xl mx-auto px-1 sm:px-0">
      <h1 className="text-xl font-bold mb-2">我的辩论</h1>
      <p className="text-sm mb-6" style={{ color: "var(--sub)" }}>
        {user.display_name || user.username} · 共 {list.length} 场
      </p>

      {loading ? (
        <div className="text-center py-12" style={{ color: "var(--sub)" }}>
          <Loader2 className="animate-spin mx-auto" size={24} />
        </div>
      ) : list.length === 0 ? (
        <div className="text-center py-12" style={{ color: "var(--sub)" }}>
          <MessageCircle size={40} className="mx-auto mb-2 opacity-30" />
          <p>还没有创建过辩论</p>
          <Link href="/create" style={{ color: "var(--accent)" }}>创建第一场</Link>
        </div>
      ) : (
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
                      <span className="flex items-center gap-1"><Users size={12} />{d.agents.length} 位</span>
                      <span className="flex items-center gap-1"><MessageCircle size={12} />{d.message_count} 条</span>
                      <span className="flex items-center gap-1"><Clock size={12} />{d.rounds} 轮</span>
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
      )}
    </div>
  );
}
