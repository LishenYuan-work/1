"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import { MessageCircle, PlusCircle, User, LogOut, LogIn } from "lucide-react";

function Navbar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  return (
    <header style={{ background: "var(--card)", borderBottom: "1px solid var(--border)" }}>
      <nav className="max-w-6xl mx-auto flex items-center justify-between px-4 h-14">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg no-underline"
          style={{ color: "var(--text)" }}>
          <MessageCircle size={22} style={{ color: "var(--accent)" }} />
          多Agent辩论室
        </Link>

        <div className="flex items-center gap-1.5 sm:gap-3 text-xs sm:text-sm">
          <Link href="/" className={`no-underline ${pathname === "/" ? "font-semibold" : ""}`}
            style={{ color: pathname === "/" ? "var(--accent)" : "var(--sub)" }}>发现</Link>
          {user ? (
            <>
              <Link href="/create" className={`no-underline ${pathname === "/create" ? "font-semibold" : ""}`}
                style={{ color: pathname === "/create" ? "var(--accent)" : "var(--sub)" }}>
                <PlusCircle size={16} className="inline mr-0.5" />创建
              </Link>
              <Link href="/dashboard" className={`no-underline ${pathname === "/dashboard" ? "font-semibold" : ""}`}
                style={{ color: pathname === "/dashboard" ? "var(--accent)" : "var(--sub)" }}>
                <User size={16} className="inline mr-0.5" />{user.display_name || user.username}
              </Link>
              <button onClick={logout} className="bg-transparent border-0 cursor-pointer"
                style={{ color: "var(--sub)" }}><LogOut size={16} /></button>
            </>
          ) : (
            <Link href="/login" style={{ color: "var(--accent)" }}
              className="no-underline font-semibold">
              <LogIn size={16} className="inline mr-0.5" />登录
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}

export function ClientLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-6">{children}</main>
    </AuthProvider>
  );
}
