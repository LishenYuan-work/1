import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  typescript: {
    ignoreBuildErrors: true, // Next.js 16 内部类型问题，待版本更新后移除
  },
};

export default nextConfig;
