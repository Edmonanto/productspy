import type { Metadata } from "next";
import Landing, { getPreview } from "@/components/landing/Landing";

export const revalidate = 600;

const TITLE = "ProductSpy Pro — Produits gagnants chaque matin pour le dropshipping";
const DESCRIPTION =
  "Chaque matin, les 5 à 10 produits que les annonceurs scalent sur ton marché — repérés dans la Bibliothèque publicitaire Facebook et sur TikTok, avec les preuves derrière chacun. Essai gratuit de 7 jours.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  keywords: [
    "produits gagnants", "dropshipping", "recherche de produits", "bibliothèque publicitaire Facebook",
    "pub TikTok", "produit gagnant Shopify", "e-commerce France",
  ],
  alternates: { canonical: "/fr", languages: { en: "/", fr: "/fr", "x-default": "/" } },
  openGraph: { type: "website", url: "/fr", siteName: "ProductSpy Pro", locale: "fr_FR", title: TITLE, description: DESCRIPTION },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION },
};

export default async function LandingPageFr() {
  return <Landing lang="fr" preview={await getPreview("FR")} />;
}
