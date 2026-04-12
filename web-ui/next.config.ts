import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    // Use runtime environment variable for API URL
    // Docker Compose sets BACKEND_API_URL to http://nd_mcp_web_api:8001
    // Fallback localhost value is useful for local non-container development
    const apiUrl = process.env.BACKEND_API_URL || 'http://localhost:8001';

    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
