"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { UserPlus, Loader2 } from "lucide-react";

export default function LoginPage() {
  const { loading, login, loginAsGuest } = useAuth();
  const router = useRouter();
  const [checked, setChecked] = useState(false);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 检查是否有保存的 token，有则直接跳转首页
  useEffect(() => {
    const saved = localStorage.getItem("token") || sessionStorage.getItem("token");
    if (saved) { router.replace("/"); return; }
    setChecked(true);
  }, []);

  if (!checked) return null; // 不渲染任何东西，直接跳转

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setSubmitting(true);
    try {
      await login(phone, password, rememberMe);
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGuest() {
    setError(""); setSubmitting(true);
    try {
      await loginAsGuest();
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "游客登录失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-sm mx-auto mt-8 sm:mt-16 px-4 sm:px-0">
      <h1 className="text-xl font-bold mb-6 text-center">登录</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <input type="tel" placeholder="手机号" value={phone}
          onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 11))}
          required pattern="1[3-9]\d{9}" maxLength={11}
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
