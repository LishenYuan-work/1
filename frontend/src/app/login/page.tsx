"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { UserPlus } from "lucide-react";

export default function LoginPage() {
  const { user, login, loginAsGuest } = useAuth();
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 已通过验证的用户自动跳转首页
  useEffect(() => {
    if (user) router.replace("/");
  }, [user]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!phone.trim() || !password.trim()) {
      setError("请输入手机号和密码"); return;
    }
    setError(""); setSubmitting(true);
    try {
      await login(phone.trim(), password, rememberMe);
      router.push("/");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "登录失败";
      setError(msg.includes("401") ? "手机号或密码错误" : msg.includes("fetch") ? "网络连接失败，请检查后端服务" : msg);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGuest() {
    setError(""); setSubmitting(true);
    try {
      // 直接 fetch 兜底，避免 context 层问题
      const BASE = process.env.NEXT_PUBLIC_API_URL || "https://1-0plp.onrender.com";
      const res = await fetch(`${BASE}/api/auth/guest`, { method: "POST" });
      if (!res.ok) throw new Error("游客登录失败");
      const data = await res.json();
      // 手动保存 token 和用户状态
      sessionStorage.setItem("token", data.access_token);
      router.push("/");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "游客登录失败";
      setError(msg.includes("fetch") || msg.includes("Failed") ? "网络连接失败，请检查后端服务" : msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-sm mx-auto mt-8 sm:mt-16 px-4 sm:px-0">
      <h1 className="text-xl font-bold mb-6 text-center">登录</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <input type="text" inputMode="numeric" placeholder="手机号" value={phone}
          onChange={(e) => setPhone(e.target.value)} required
          className="px-3 py-2 rounded-lg border text-sm"
          style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }} />
        <input type="password" placeholder="密码" value={password}
          onChange={(e) => setPassword(e.target.value)} required minLength={6}
          className="px-3 py-2 rounded-lg border text-sm"
          style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }} />
        <label className="flex items-center gap-2 text-xs cursor-pointer" style={{ color: "var(--sub)" }}>
          <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)}
            style={{ accentColor: "var(--accent)" }} /> 7 天内免登录
        </label>
        {error && <p className="text-red-500 text-sm m-0">{error}</p>}
        <button type="submit" disabled={submitting}
          className="py-2 rounded-lg text-white font-semibold border-0 cursor-pointer disabled:opacity-50"
          style={{ background: "var(--accent)" }}>{submitting ? "登录中…" : "登录"}</button>
      </form>
      <div className="mt-3">
        <button onClick={handleGuest} disabled={submitting}
          className="w-full py-2 rounded-lg font-semibold border cursor-pointer disabled:opacity-50 text-sm flex items-center justify-center gap-1"
          style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }}>
          <UserPlus size={16} /> 游客模式（无需注册）
        </button>
      </div>
      <p className="text-center text-sm mt-4" style={{ color: "var(--sub)" }}>
        没有账号？<Link href="/register" style={{ color: "var(--accent)" }}>注册</Link>
      </p>
    </div>
  );
}
