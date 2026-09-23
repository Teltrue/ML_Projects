import type { NextConfig } from "next";

// The browser talks to the FastAPI engines through this same-origin proxy, so there is no
// CORS setup and the backend URL is a server-side concern only.
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
