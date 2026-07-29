"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import type { UserProfile } from "./api";
import { auth } from "./api";

interface AuthState {
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  user: null, token: null, loading: true,
  login: async () => {}, register: async () => {}, logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem("token");
    if (saved) {
      setToken(saved);
      auth.me().then((u) => setUser(u)).catch(() => {
        localStorage.removeItem("token");
        setToken(null);
      }).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const loginFn = useCallback(async (username: string, password: string) => {
    const res = await auth.login({ username, password });
    localStorage.setItem("token", res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const registerFn = useCallback(async (username: string, password: string, displayName?: string) => {
    const res = await auth.register({ username, password, display_name: displayName });
    localStorage.setItem("token", res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login: loginFn, register: registerFn, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
