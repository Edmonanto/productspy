import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { Suspense } from "react";
import { AuthProvider } from "@/context/AuthContext";
import RefCapture from "@/components/partners/RefCapture";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

const TITLE = "ProductSpy Pro — Daily Winning Products for Dropshippers";
const DESCRIPTION =
  "Every morning, the 5–10 products advertisers are scaling in your market — read from the Facebook Ad Library and TikTok, with the evidence behind each pick. 7-day free trial.";

export const metadata: Metadata = {
  metadataBase: new URL("https://productspy.pro"),
  title: { default: TITLE, template: "%s" },
  description: DESCRIPTION,
  applicationName: "ProductSpy Pro",
  keywords: [
    "winning products", "dropshipping product research", "Facebook ad library", "TikTok ads",
    "product research tool", "Shopify winning products", "TikTok made me buy it",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website", url: "/", siteName: "ProductSpy Pro", title: TITLE, description: DESCRIPTION,
  },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION },
};

export const viewport: Viewport = { themeColor: "#09090b" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-zinc-950 text-white antialiased`}>
        <AuthProvider>{children}<Suspense fallback={null}><RefCapture /></Suspense></AuthProvider>
      </body>
    </html>
  );
}
