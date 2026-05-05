import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // All API routes now have local handlers in app/api/*
  // No rewrites needed — each route proxies to backend as needed
};

export default nextConfig;
