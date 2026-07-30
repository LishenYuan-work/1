import type { NextConfig } from "next";
import { setupDevPlatform } from "@cloudflare/next-on-pages/next-dev";

const nextConfig: NextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
};

// Cloudflare Pages 本地开发用
if (process.env.NODE_ENV === "development") {
  setupDevPlatform().catch(() => {});
}

export default nextConfig;
