/** @type {import("next").NextConfig} */

/**
 * next.config.js
 *
 * Next.js configuration for the RAG Knowledge Assistant frontend.
 * Sets up API URL env variable and proxies backend API calls through
 * Next.js rewrites to avoid CORS issues in production Docker networking.
 */

const nextConfig = {
  reactStrictMode: true,
  output: "standalone",

  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },

  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_INTERNAL_URL || "http://backend:8000"}/:path*`,
      },
    ];
  },

  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
    ],
  },
};

module.exports = nextConfig;
