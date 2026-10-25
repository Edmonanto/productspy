import { IMAGE_HOSTS } from "./image-hosts.mjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emit a self-contained server bundle at .next/standalone for the Docker runner stage.
  output: "standalone",
  images: {
    remotePatterns: IMAGE_HOSTS.map((hostname) => ({ protocol: "https", hostname })),
  },
};

export default nextConfig;
