// AeroLaminate Pro - Next.js configuration. Author: Anwesh Ajitabh Dash.
// API calls go to /api/* and are proxied to the local FastAPI engine, so the browser needs no CORS.
const backend = process.env.AEROLAMINATE_API ?? "http://127.0.0.1:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
export default nextConfig;
