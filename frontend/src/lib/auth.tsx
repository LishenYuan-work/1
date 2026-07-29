"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import type { UserProfile } from "./api";
import { auth } from "./api";

interface AuthState {
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
  login: (phone: string, password: string, rememberMe?: boolean) => Promise<void>;
  register: (phone: string, password: string, displayName?: string) => Promise<void>;
  loginAsGuest: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  user: null, token: null, loading: true,
  login: async () => {}, register: async () => {}, loginAsGuest: async () => {}, logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // 自动恢复登录状态（容错：冷启动超时不踢人）
  useEffect(() => {
    let cancelled = false;

    async function restore() {
      // 优先用 sessionStorage（游客），其次 localStorage（注册用户）
      const saved = sessionStorage.getItem("token") || localStorage.getItem("token");
      if (!saved) { setLoading(false); return; }

      setToken(saved);
      // 重试 3 次，应对 Render 冷启动
      for (let i = 0; i < 3; i++) {
        try {
          const u = await auth.me();
          if (!cancelled) {
            setUser(u);
            setLoading(false);
          }
          return;
        } catch {
          if (i < 2) await new Promise((r) => setTimeout(r, 2000)); // 等 2 秒重试
        }
      }
      // 3 次都失败，不踢人，保留 token 继续用
      if (!cancelled) setLoading(false);
    }

    restore();
    return () => { cancelled = true; };
  }, []);

  const saveToken = useCallback((t: string, guest: boolean) => {
    setToken(t);
    if (guest) {
      sessionStorage.setItem("token", t);  // 游客用 sessionStorage，关闭浏览器即清除
      localStorage.removeItem("token");
    } else {
      localStorage.setItem("token", t);   // 注册用户用 localStorage，7天有效
      sessionStorage.removeItem("token");
    }
  }, []);

  const loginFn = useCallback(async (phone: string, password: string, rememberMe = true) => {
    const res = await auth.login({ phone, password, remember_me: rememberMe });
    saveToken(res.access_token, false);
    setUser(res.user);
  }, [saveToken]);

  const registerFn = useCallback(async (phone: string, password: string, displayName?: string) => {
    const res = await auth.register({ phone, password, display_name: displayName });
    saveToken(res.access_token, false);
    setUser(res.user);
  }, [saveToken]);

  const guestFn = useCallback(async () => {
    const res = await auth.guest();
    saveToken(res.access_token, true);
    setUser(res.user);
  }, [saveToken]);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    sessionStorage.removeItem("token");
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{
      user, token, loading,
      login: loginFn, register: registerFn, loginAsGuest: guestFn, logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
