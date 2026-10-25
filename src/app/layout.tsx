import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AuthProvider } from "@/context/AuthContext";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ProductSpy Pro — Daily Winning Products for Dropshippers",
  description: "Every morning, the 5–10 products advertisers are scaling in your market — read from the Facebook Ad Library, TikTok Top Ads and TikTok, with the evidence behind each pick. 7-day free trial.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-zinc-950 text-white antialiased`}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
