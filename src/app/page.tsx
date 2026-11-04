import type { Metadata } from "next";
import Landing, { getPreview } from "@/components/landing/Landing";

export const revalidate = 600;

export const metadata: Metadata = {
  alternates: { canonical: "/", languages: { en: "/", fr: "/fr", "x-default": "/" } },
};

export default async function LandingPage() {
  return <Landing lang="en" preview={await getPreview()} />;
}
