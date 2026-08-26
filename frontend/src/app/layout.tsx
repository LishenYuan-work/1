import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
export const metadata: Metadata = { title: "多 Agent 交叉评审", description: "面向团队的方案交叉评审调研平台" };
export default function RootLayout({ children }: { children: React.ReactNode }) { return <html lang="zh-CN"><body><AuthProvider>{children}</AuthProvider></body></html>; }
