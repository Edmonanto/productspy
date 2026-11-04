import type { Metadata } from "next";
import type { Lang } from "@/content/landing-copy";
import SignupForm from "./SignupForm";

/** Server wrapper: reads ?lang= so French visitors (from /fr) get a French page
 *  on first paint, with no English flash. */
export function generateMetadata({ searchParams }: { searchParams: { lang?: string } }): Metadata {
  return searchParams.lang === "fr"
    ? { title: "Créer un compte — ProductSpy Pro", alternates: { canonical: "/signup" } }
    : { title: "Create your account — ProductSpy Pro" };
}

export default function SignupPage({ searchParams }: { searchParams: { lang?: string } }) {
  const lang: Lang = searchParams.lang === "fr" ? "fr" : "en";
  return <div lang={lang}><SignupForm lang={lang} /></div>;
}
