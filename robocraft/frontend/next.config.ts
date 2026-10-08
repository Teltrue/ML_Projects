import type { NextConfig } from "next";

// The browser talks to the FastAPI engines through this same-origin proxy, so there is no
// CORS setup and the backend URL is a server-side concern only.
const onVercel = Boolean(process.env.VERCEL);
if (onVercel && !process.env.BACKEND_URL) {
  throw new Error(
    "BACKEND_URL is not set. In the Vercel project settings, add an environment variable " +
      "BACKEND_URL pointing at the RoboCraft API deployment (for example " +
      "https://robocraft-api.vercel.app), then redeploy.",
  );
}
const backend = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  // Vercel packages the app itself; the standalone server is for the Docker image.
  output: onVercel ? undefined : "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
