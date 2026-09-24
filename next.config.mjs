/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emit a self-contained server bundle at .next/standalone for the Docker runner stage.
  output: "standalone",
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "images.unsplash.com" },
      { protocol: "https", hostname: "**.aliexpress.com" },
      { protocol: "https", hostname: "**.alicdn.com" },
      { protocol: "https", hostname: "**.tiktokcdn.com" },
      // TikTok Shop serves product images from ttcdn-us.com, not
      // tiktokcdn.com. Without this every TikTok image 400s.
      { protocol: "https", hostname: "**.ttcdn-us.com" },
      { protocol: "https", hostname: "**.amazon.com" },
      { protocol: "https", hostname: "m.media-amazon.com" },
    ],
  },
};

export default nextConfig;
