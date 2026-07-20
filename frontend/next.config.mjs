/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone output produces a minimal, self-contained server for Docker.
  output: 'standalone',
  poweredByHeader: false,
  eslint: {
    // Lint is enforced as a separate CI step; don't fail the build twice.
    ignoreDuringBuilds: false,
  },
  async rewrites() {
    // Proxy API calls to the backend in development (Nginx handles this in prod).
    const backend = process.env.BACKEND_INTERNAL_URL || 'http://localhost:8000';
    return [{ source: '/api/:path*', destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
