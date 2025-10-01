/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  output: 'standalone',
  // API routing is now handled by nginx reverse proxy
  // No need for rewrites since nginx routes /api/nl2sql/ to the backend
}

module.exports = nextConfig
