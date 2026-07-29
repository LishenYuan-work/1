"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { UserPlus } from "lucide-react";

export default function LoginPage() {
  const { login, loginAsGuest } = useAuth();
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await login(phone, password, rememberMe);
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleGuest() {
    setError(""); setLoading(true);
    try {
      await loginAsGuest();
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "游客登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-sm mx-auto mt-8 sm:mt-16 px-4 sm:px-0">
      <h1 className="text-xl font-bold mb-6 text-center">登录</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <input
          type="tel" placeholder="手机号" value={phone}
          onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 11))}
          required pattern="1[3-9]\d{9}" maxLength={11}
          className="px-3 py-2 rounded-lg border text-sm"
          style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }}
        />
        <input
          type="password" placeholder="密码" value={password}
          onChange={(e) => setPassword(e.target.value)} required minLength={6}
          className="px-3 py-2 rounded-lg border text-sm"
          style={{ borderColor: "var(--border)", background: "var(--card)", color: "var(--text)" }}
        />
        <label className="flex items-center gap-2 text-xs cursor-pointer" style={{ color: "var(--sub)" }}>
          <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)}
            style={{ accentColor: "var(--accent)" }} />
          7 天内免登录
        </label>
        {error && <p className="text-red-500 text-sm m-0">{error}</p>}
        <button type="submit" disabled={loading}
          className="py-2 rounded-lg text-white font-semibold border-0 cursor-pointer disabled:opacity-50"
          style={{ background: "var(--accent)" }}>
          {loading ? "登录中…" : "登录"}
        </button>
      </form>

      <div className="mt-3">
        <button onClick={handleGuest} disabled={loading}
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
