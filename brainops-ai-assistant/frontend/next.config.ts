import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactStrictMode: true,
  swcMinify: true,
  
  // Enable PWA features
  headers: async () => [
    {
      source: '/service-worker.js',
      headers: [
        {
          key: 'Service-Worker-Allowed',
          value: '/',
        },
      ],
    },
  ],
  
  // Allow service worker scope
  async rewrites() {
    return [
      {
        source: '/sw.js',
        destination: '/service-worker.js',
      },
    ];
  },
};

export default nextConfig;
