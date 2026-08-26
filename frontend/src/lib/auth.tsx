"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { api, type UserProfile } from "./api";

type AuthState = { user: UserProfile | null; loading: boolean; login: (email: string, password: string) => Promise<void>; register: (data: Parameters<typeof api.auth.register>[0]) => Promise<void>; logout: () => void; };
const Context = createContext<AuthState>({ user: null, loading: true, login: async () => {}, register: async () => {}, logout: () => {} });
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null); const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.auth.me()
      .catch(async () => {
        await api.auth.refresh();
        return api.auth.me();
      })
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);
  async function login(email: string, password: string) { const result = await api.auth.login({ email, password, remember_me: true }); setUser(result.user); }
  async function register(data: Parameters<typeof api.auth.register>[0]) { const result = await api.auth.register(data); if (!result.user.email_verified) throw new Error("注册成功，请先验证邮箱后再登录。验证链接已发送到您的邮箱。"); setUser(result.user); }
  return <Context.Provider value={{ user, loading, login, register, logout: () => { api.auth.logout().catch(() => undefined); setUser(null); } }}>{children}</Context.Provider>;
}
export const useAuth = () => useContext(Context);
