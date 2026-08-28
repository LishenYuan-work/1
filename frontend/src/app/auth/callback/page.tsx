"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  useEffect(() => {
    let mounted = true;
    const run = async () => {
      if (!supabase) { setError("Supabase Auth 尚未配置"); return; }
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      if (code) {
        const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
        if (exchangeError) { if (mounted) setError(exchangeError.message); return; }
      }
      router.replace(params.get("next") || "/");
    };
    void run();
    return () => { mounted = false; };
  }, [router]);
  return <main className="auth-shell"><section className="auth-card"><div className="brand"><span className="brand-mark">R</span> 多 Agent 交叉评审</div><h1>{error ? "登录链接无效" : "正在完成登录"}</h1><p>{error || "请稍候，正在建立安全会话。"}</p></section></main>;
}
