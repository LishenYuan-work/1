"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(username, password, displayName || undefined);
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "注册失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-sm mx-auto mt-8 sm:mt-16 px-4 sm:px-0">
      <h1 className="text-xl font-bold mb-6 text-center">注册</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <input
          type="text" placeholder="用户名" value={username}
          onChange={(e) => setUsername(e.target.value)} required minLength={2}
          className="px-3 py-2 rounded-lg border text-sm"
          style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }}
        />
        <input
          type="text" placeholder="显示名称（可选）" value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="px-3 py-2 rounded-lg border text-sm"
          style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }}
        />
        <input
          type="password" placeholder="密码（至少6位）" value={password}
          onChange={(e) => setPassword(e.target.value)} required minLength={6}
          className="px-3 py-2 rounded-lg border text-sm"
          style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }}
        />
        {error && <p className="text-red-500 text-sm m-0">{error}</p>}
        <button type="submit" disabled={loading}
          className="py-2 rounded-lg text-white font-semibold border-0 cursor-pointer disabled:opacity-50"
          style={{ background: "var(--accent)" }}>
          {loading ? "注册中…" : "注册"}
        </button>
      </form>
      <p className="text-center text-sm mt-4" style={{ color: "var(--sub)" }}>
        已有账号？<Link href="/login" style={{ color: "var(--accent)" }}>登录</Link>
      </p>
    </div>
  );
}
