/** @type {import('next').NextConfig} */
const nextConfig = {
  // All API calls are server-side — no rewrites needed
  // Disable image optimization for simple deployment
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
