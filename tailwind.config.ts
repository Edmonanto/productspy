import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
      colors: {
        // Lighter than Tailwind's #71717a so secondary text passes WCAG AA
        // (4.5:1) on the zinc-900/950 backgrounds used everywhere.
        zinc: { 500: "#93939c" },
      },
    },
  },
  plugins: [],
};

export default config;
