/**
 * Landing page copy, English and French. `/` renders "en", `/fr` renders "fr".
 * French uses "tu", like the Instagram posts. Keep both languages in step:
 * the type makes a missing French string a type error.
 */
import type { CriterionKey } from "@/lib/utils";

export type Lang = "en" | "fr";

type Plan = { name: string; price: string; per: string; desc: string; cta: string; highlight: boolean; contact?: boolean; features: string[] };

export interface LandingCopy {
  lang: Lang;
  home: string;                       // this language's landing path
  switchTo: { label: string; href: string; title: string };
  defaultMarket: string;
  locale: string;                     // for dates
  nav: { picks: string; features: string; calculator: string; pricing: string; signIn: string; start: string };
  hero: { badge: string; h1a: string; h1b: string; sub: string; cta: string; secondary: string; checks: string[] };
  steps: { title: string; desc: string }[];
  features: { heading: string; sub: string; note: string; items: { title: string; desc: string }[] };
  examples: {
    angles: [string, string][];
    trend: string;
    profit: [string, string][];       // label, value
    report: string[];
    compare: string[];
    labels: { radar: string; angles: string; trend: string; profit: string; report: string; compare: string };
  };
  score: { heading: string; body: string; note: string; criteria: [string, number][] };
  calc: {
    badge: string; heading: string; sub: string;
    sellFor: string; supplierCost: string; adCost: string;
    includes: (a: { shipping: number; packaging: string; feePct: number; feeFixed: string; returnsPct: number }) => string;
    profit: string; good: string; bad: string; maxCpa: string; roas: string;
  };
  vs: { heading: string; byHand: string; rows: [string, string, string][] };
  reviews: {
    heading: string; from: (avg: string, n: number) => string;
    emptyHeading: string; emptyBody: string; emptyCta: string;
  };
  trusted: { customers: string; sources: string; disclaimer: string; items: { name: string; desc: string }[] };
  pricing: { heading: string; sub: string; popular: string; plans: Plan[] };
  partner: { heading: string; body: [string, string, string, string, string]; cta: string };
  faqHeading: string;
  faq: [string, string][];
  final: { heading: string; sub: string; cta: string };
  live: {
    today: string; market: string; waking: string; running: string;
    more: (n: number) => string; seeAll: string; unlock: string; pick: (n: number) => string;
    freePick: string; topPick: string; stores: (n: number) => string; daysAds: (n: number) => string;
  };
  footer: { privacy: string; terms: string; contact: string };
  trend: Record<string, string>;
  radar: Record<CriterionKey, string>;
}

const EN: LandingCopy = {
  lang: "en",
  home: "/",
  switchTo: { label: "FR", href: "/fr", title: "Version française" },
  defaultMarket: "US",
  locale: "en-US",
  nav: { picks: "Today's picks", features: "Features", calculator: "Profit calculator", pricing: "Pricing", signIn: "Sign in", start: "Start free" },
  hero: {
    badge: "New winners every morning · US · UK · France",
    h1a: "Stop guessing.",
    h1b: "Sell what's already winning.",
    sub: "Every night we scan thousands of Facebook and TikTok ads. Every morning you get the 5–10 products advertisers are scaling — scored, with the proof.",
    cta: "Start 7-day free trial",
    secondary: "See today's picks",
    checks: ["No credit card", "Sign up with Google in 10 s", "Cancel anytime"],
  },
  steps: [
    { title: "We scan", desc: "Facebook Ad Library + TikTok, every night, per country." },
    { title: "AI filters", desc: "Real products only. Duplicates merged, brands and risky items out." },
    { title: "You get winners", desc: "5–10 scored picks every morning, with the proof behind each." },
  ],
  features: {
    heading: "Everything behind every pick",
    sub: "Not just a product name — the full case to test it (or skip it).",
    note: "Illustrations. Inside the app every number comes from real ads and data.",
    items: [
      { title: "8-criteria score", desc: "See exactly why it scores high — and where it's weak." },
      { title: "Ad angles & hooks", desc: "3–5 ready-to-film angles for every product." },
      { title: "Google Trends", desc: "Rising, stable or fading — before you spend." },
      { title: "Profit calculator", desc: "Break-even ad cost and ROAS, per product." },
      { title: "AI research report", desc: "12 sections, every claim linked to its source." },
      { title: "Compare products", desc: "Put picks side by side and choose in seconds." },
    ],
  },
  examples: {
    angles: [["Problem → solution", "“I wasted $200 before finding this”"], ["Before / after", "“Watch what happens in 10 seconds”"], ["Gift idea", "“The gift she didn't know she needed”"]],
    trend: "▲ Rising · +140% in 90 days (example)",
    profit: [["Profit / order", "$9.40"], ["Break-even ROAS", "1.6×"], ["Max CPA", "$21.80"], ["Margin", "62%"]],
    report: ["Demand & trend", "Competitors & prices", "Target customer", "Risks & red flags", "Verdict: test it"],
    compare: ["Product A", "Product B", "Product C"],
    labels: { radar: "Example score radar", angles: "Example ad angles", trend: "Example search trend", profit: "Example profit numbers", report: "Example research report", compare: "Example comparison" },
  },
  score: {
    heading: "One honest score, 8 criteria",
    body: "Missing data never counts as good news. Saturated products, brand copies and restricted items are removed before scoring.",
    note: "Winners need 70+ and enough evidence.",
    // Same 8 criteria and weights as backend/app/winners/scoring.py.
    criteria: [["Demand & trend", 20], ["Profitability", 20], ["Competition", 15], ["Creative potential", 10],
      ["Differentiation", 10], ["Logistics", 10], ["Market fit", 10], ["Risk", 5]],
  },
  calc: {
    badge: "FREE · NO SIGNUP",
    heading: "Will this product make you money?",
    sub: "Move the sliders. Know your break-even before you spend a dollar on ads.",
    sellFor: "You sell it for", supplierCost: "Supplier cost", adCost: "Ad cost per sale",
    includes: (a) => `Includes $${a.shipping} shipping, $${a.packaging} packaging, ${a.feePct}% + $${a.feeFixed} payment fees and ${a.returnsPct}% returns.`,
    profit: "Profit per order", good: "This product can work.", bad: "You lose money on every sale.",
    maxCpa: "Max ad cost per sale", roas: "Break-even ROAS",
  },
  vs: {
    heading: "Your mornings, before and after",
    byHand: "By hand",
    rows: [
      ["Time per day", "2–3 hours scrolling ads", "5 minutes"],
      ["How you choose", "Gut feeling", "Score out of 100 on 8 criteria"],
      ["Ad proof", "Screenshot hunting", "Days running, versions, stores"],
      ["Profit check", "Spreadsheet", "Built in, per product"],
      ["Ad ideas", "Copy competitors", "3–5 angles + hooks per product"],
    ],
  },
  reviews: {
    heading: "What dropshippers say",
    from: (avg, n) => `${avg} / 5 from ${n} review${n === 1 ? "" : "s"}`,
    emptyHeading: "Be one of our first reviewers",
    emptyBody: "ProductSpy Pro is new, so you won't find a wall of testimonials here yet — and we won't invent one. Try it free for 7 days, test a pick or two, and tell us honestly how it went. Early users help shape what we build next.",
    emptyCta: "Join early access",
  },
  trusted: {
    customers: "Trusted by dropshippers and stores like",
    sources: "Built on the public data serious dropshippers already check by hand",
    disclaimer: "ProductSpy is independent and not affiliated with or endorsed by Meta, TikTok or AliExpress.",
    items: [
      { name: "Facebook Ad Library", desc: "Ads running in your market" },
      { name: "TikTok", desc: "Product videos and comments" },
      { name: "AliExpress", desc: "Supplier costs" },
    ],
  },
  pricing: {
    heading: "Less than one failed product test",
    sub: "Every account starts with 7 days of Pro, free. No card. Cancel anytime.",
    popular: "MOST POPULAR",
    plans: [
      { name: "Free", price: "$0", per: "", desc: "After your trial", cta: "Start free", highlight: false,
        features: ["Top 3 winners a day", "1 market", "Score + reasons", "Watchlist (10)"] },
      { name: "Starter", price: "$19.99", per: "/mo", desc: "For one store", cta: "Start with Starter", highlight: false,
        features: ["All 5–10 winners daily", "1 market", "Ads & video proof", "3–5 ad angles per product", "5 AI reports a day", "7-day archive"] },
      { name: "Pro", price: "$69.99", per: "/mo", desc: "For serious sellers", cta: "Start 7-day free trial", highlight: true,
        features: ["Everything in Starter", "All 3 markets", "Suppliers + Google Trends", "20 AI reports a day", "30-day archive + CSV", "Priority support"] },
      { name: "Agency", price: "$199", per: "/mo", desc: "For teams & coaches", cta: "Contact us", highlight: false, contact: true,
        features: ["Everything in Pro", "Every new market", "100 AI reports a day", "90-day archive", "Dedicated support"] },
    ],
  },
  partner: { heading: "Dropshipping coach or community?", body: ["Earn ", "30% for 12 months", " on every student. They get ", "25% off", " their first month."], cta: "Become a partner" },
  faqHeading: "Questions",
  faq: [
    ["Do I need an account?", "No, not to look around. Today's #1 pick and the profit calculator on this page are free. A free account (Google, 10 seconds, no card) starts your 7 days of Pro: the full list, the ads, suppliers, Google Trends and AI research. After the trial, the Free plan keeps the top 3 picks a day."],
    ["Do I need a credit card for the trial?", "No. You get 7 days of Pro free. After that you stay on the Free plan unless you choose a paid one."],
    ["Where does the data come from?", "The public Facebook Ad Library, TikTok and Google Trends — the same places pros check by hand, scanned for you every night."],
    ["Which countries?", "United States, United Kingdom and France today. Germany, Canada, Australia and the Gulf are next."],
    ["Can I cancel anytime?", "Yes, in one click from your billing page. You keep access until the end of the month you paid for."],
    ["I'm a dropshipping coach. Can I partner?", "Yes. You earn 30% of every payment for 12 months, and your students get 25% off their first month."],
  ],
  final: { heading: "Tomorrow morning, your first winners.", sub: "7 days of Pro free. No card. Takes 10 seconds.", cta: "Start free" },
  live: {
    today: "Today's winners", market: "Market",
    waking: "The live list is waking up — try again in a few seconds.",
    running: "Today's scan for this market is still running. Picks land every morning.",
    more: (n) => `+${n} more winners today with their ads, stores, suppliers and margins`,
    seeAll: "See them all free", unlock: "Unlock free", pick: (n) => `Pick #${n}`,
    freePick: "#1 · FREE PICK OF THE DAY", topPick: "Today's top pick",
    stores: (n) => `${n} stores`, daysAds: (n) => `${n} days of ads`,
  },
  footer: { privacy: "Privacy", terms: "Terms", contact: "Contact" },
  trend: { emerging: "Emerging", growing: "Growing", stable: "Stable", declining: "Declining", spike: "Viral spike", seasonal: "Seasonal", unknown: "Trend unclear" },
  radar: { demand: "Demand", profitability: "Profit", competition: "Compet.", creative: "Creative", differentiation: "Offer", logistics: "Logistics", market_fit: "Market", risk: "Risk" },
};

const FR: LandingCopy = {
  lang: "fr",
  home: "/fr",
  switchTo: { label: "EN", href: "/", title: "English version" },
  defaultMarket: "FR",
  locale: "fr-FR",
  nav: { picks: "Produits du jour", features: "Fonctionnalités", calculator: "Calculateur de marge", pricing: "Tarifs", signIn: "Connexion", start: "Essai gratuit" },
  hero: {
    badge: "De nouveaux produits gagnants chaque matin · France · UK · US",
    h1a: "Arrête de deviner.",
    h1b: "Vends ce qui marche déjà.",
    sub: "Chaque nuit, on analyse des milliers de pubs Facebook et TikTok. Chaque matin, tu reçois les 5 à 10 produits que les annonceurs sont en train de scaler — notés, avec les preuves.",
    cta: "Essai gratuit de 7 jours",
    secondary: "Voir les produits du jour",
    checks: ["Sans carte bancaire", "Inscription Google en 10 s", "Sans engagement"],
  },
  steps: [
    { title: "On analyse", desc: "La Bibliothèque publicitaire Facebook + TikTok, chaque nuit, pays par pays." },
    { title: "L'IA filtre", desc: "Uniquement de vrais produits. Doublons fusionnés, marques et produits à risque écartés." },
    { title: "Tu reçois les gagnants", desc: "5 à 10 produits notés chaque matin, avec les preuves derrière chacun." },
  ],
  features: {
    heading: "Tout ce qu'il y a derrière chaque produit",
    sub: "Pas juste un nom de produit — tout ce qu'il faut pour décider de le tester (ou pas).",
    note: "Illustrations. Dans l'appli, chaque chiffre vient de vraies pubs et de vraies données.",
    items: [
      { title: "Note sur 8 critères", desc: "Vois exactement pourquoi il a une bonne note — et où il pèche." },
      { title: "Angles pub & accroches", desc: "3 à 5 angles prêts à tourner pour chaque produit." },
      { title: "Google Trends", desc: "En hausse, stable ou en baisse — avant de dépenser." },
      { title: "Calculateur de marge", desc: "Coût pub max et ROAS d'équilibre, produit par produit." },
      { title: "Rapport d'analyse IA", desc: "12 sections, chaque affirmation reliée à sa source." },
      { title: "Comparer des produits", desc: "Mets des produits côte à côte et choisis en quelques secondes." },
    ],
  },
  examples: {
    angles: [["Problème → solution", "« J'ai perdu 200 € avant de trouver ça »"], ["Avant / après", "« Regarde ce qui se passe en 10 secondes »"], ["Idée cadeau", "« Le cadeau dont elle ne savait pas avoir besoin »"]],
    trend: "▲ En hausse · +140 % en 90 jours (exemple)",
    profit: [["Bénéfice / commande", "9,40 $"], ["ROAS d'équilibre", "1,6×"], ["CPA max", "21,80 $"], ["Marge", "62 %"]],
    report: ["Demande & tendance", "Concurrents & prix", "Client cible", "Risques & signaux d'alerte", "Verdict : à tester"],
    compare: ["Produit A", "Produit B", "Produit C"],
    labels: { radar: "Exemple de radar de note", angles: "Exemples d'angles pub", trend: "Exemple de tendance de recherche", profit: "Exemple de chiffres de marge", report: "Exemple de rapport d'analyse", compare: "Exemple de comparaison" },
  },
  score: {
    heading: "Une note honnête, 8 critères",
    body: "Une donnée manquante ne compte jamais comme une bonne nouvelle. Les produits saturés, les copies de marques et les produits interdits sont retirés avant la notation.",
    note: "Un produit gagnant doit avoir 70+ et assez de preuves.",
    criteria: [["Demande & tendance", 20], ["Rentabilité", 20], ["Concurrence", 15], ["Potentiel créatif", 10],
      ["Différenciation", 10], ["Logistique", 10], ["Adéquation marché", 10], ["Risque", 5]],
  },
  calc: {
    badge: "GRATUIT · SANS INSCRIPTION",
    heading: "Ce produit va-t-il te rapporter de l'argent ?",
    sub: "Bouge les curseurs. Connais ton seuil de rentabilité avant de dépenser un euro en pub.",
    sellFor: "Prix de vente", supplierCost: "Coût fournisseur", adCost: "Coût pub par vente",
    includes: (a) => `Inclut ${a.shipping} $ de livraison, ${a.packaging.replace(".", ",")} $ d'emballage, ${a.feePct} % + ${a.feeFixed.replace(".", ",")} $ de frais de paiement et ${a.returnsPct} % de retours.`,
    profit: "Bénéfice par commande", good: "Ce produit peut marcher.", bad: "Tu perds de l'argent à chaque vente.",
    maxCpa: "Coût pub max par vente", roas: "ROAS d'équilibre",
  },
  vs: {
    heading: "Tes matins, avant et après",
    byHand: "À la main",
    rows: [
      ["Temps par jour", "2 à 3 heures à scroller des pubs", "5 minutes"],
      ["Comment tu choisis", "Au feeling", "Une note sur 100, 8 critères"],
      ["Preuve pub", "Chasse aux captures d'écran", "Jours de diffusion, versions, boutiques"],
      ["Calcul de marge", "Tableur", "Intégré, pour chaque produit"],
      ["Idées de pub", "Copier les concurrents", "3 à 5 angles + accroches par produit"],
    ],
  },
  reviews: {
    heading: "Ce qu'en disent les dropshippers",
    from: (avg, n) => `${avg.replace(".", ",")} / 5 sur ${n} avis`,
    emptyHeading: "Sois parmi nos premiers avis",
    emptyBody: "ProductSpy Pro est tout nouveau : tu ne trouveras pas encore de mur de témoignages ici — et on ne va pas en inventer. Essaie gratuitement pendant 7 jours, teste un ou deux produits, et dis-nous franchement comment ça s'est passé. Les premiers utilisateurs nous aident à décider de la suite.",
    emptyCta: "Rejoindre l'accès anticipé",
  },
  trusted: {
    customers: "Ils nous font confiance",
    sources: "Basé sur les données publiques que les dropshippers sérieux vérifient déjà à la main",
    disclaimer: "ProductSpy est indépendant et n'est ni affilié à Meta, TikTok ou AliExpress, ni approuvé par eux.",
    items: [
      { name: "Bibliothèque publicitaire Facebook", desc: "Les pubs diffusées sur ton marché" },
      { name: "TikTok", desc: "Vidéos produits et commentaires" },
      { name: "AliExpress", desc: "Coûts fournisseurs" },
    ],
  },
  pricing: {
    heading: "Moins cher qu'un seul test produit raté",
    sub: "Chaque compte commence avec 7 jours de Pro offerts. Sans carte. Sans engagement. Prix en dollars US.",
    popular: "LE PLUS CHOISI",
    plans: [
      { name: "Free", price: "0 $", per: "", desc: "Après ton essai", cta: "Commencer gratuitement", highlight: false,
        features: ["Top 3 des gagnants par jour", "1 marché", "Note + raisons", "Liste de suivi (10)"] },
      { name: "Starter", price: "19,99 $", per: "/mois", desc: "Pour une boutique", cta: "Choisir Starter", highlight: false,
        features: ["Les 5 à 10 gagnants chaque jour", "1 marché", "Preuves pubs & vidéos", "3 à 5 angles pub par produit", "5 rapports IA par jour", "Archives 7 jours"] },
      { name: "Pro", price: "69,99 $", per: "/mois", desc: "Pour les vendeurs sérieux", cta: "Essai gratuit de 7 jours", highlight: true,
        features: ["Tout Starter", "Les 3 marchés", "Fournisseurs + Google Trends", "20 rapports IA par jour", "Archives 30 jours + CSV", "Support prioritaire"] },
      { name: "Agency", price: "199 $", per: "/mois", desc: "Pour les équipes & coachs", cta: "Nous contacter", highlight: false, contact: true,
        features: ["Tout Pro", "Chaque nouveau marché", "100 rapports IA par jour", "Archives 90 jours", "Support dédié"] },
    ],
  },
  partner: { heading: "Coach dropshipping ou communauté ?", body: ["Gagne ", "30 % pendant 12 mois", " sur chaque élève. Ils ont ", "25 % de réduction", " sur leur premier mois."], cta: "Devenir partenaire" },
  faqHeading: "Questions fréquentes",
  faq: [
    ["Faut-il un compte ?", "Non, pas pour regarder. Le produit n°1 du jour et le calculateur de marge sur cette page sont gratuits. Un compte gratuit (Google, 10 secondes, sans carte) lance tes 7 jours de Pro : la liste complète, les pubs, les fournisseurs, Google Trends et l'analyse IA. Après l'essai, l'offre Free garde le top 3 du jour."],
    ["Faut-il une carte bancaire pour l'essai ?", "Non. Tu as 7 jours de Pro offerts. Ensuite, tu restes sur l'offre Free, sauf si tu choisis une offre payante."],
    ["D'où viennent les données ?", "De la Bibliothèque publicitaire Facebook, de TikTok et de Google Trends — les mêmes sources que les pros vérifient à la main, analysées pour toi chaque nuit."],
    ["Quels pays ?", "La France, le Royaume-Uni et les États-Unis aujourd'hui. L'Allemagne, le Canada, l'Australie et le Golfe arrivent ensuite."],
    ["Puis-je résilier à tout moment ?", "Oui, en un clic depuis ta page de facturation. Tu gardes l'accès jusqu'à la fin du mois payé."],
    ["L'appli est-elle en français ?", "Cette page oui. Le tableau de bord est en anglais pour l'instant ; la version française arrive bientôt."],
    ["Je suis coach dropshipping. Puis-je devenir partenaire ?", "Oui. Tu gagnes 30 % de chaque paiement pendant 12 mois, et tes élèves ont 25 % de réduction sur leur premier mois."],
  ],
  final: { heading: "Demain matin, tes premiers produits gagnants.", sub: "7 jours de Pro offerts. Sans carte. 10 secondes.", cta: "Commencer gratuitement" },
  live: {
    today: "Les gagnants du jour", market: "Marché",
    waking: "La liste se réveille — réessaie dans quelques secondes.",
    running: "L'analyse du jour pour ce marché tourne encore. Les produits arrivent chaque matin.",
    more: (n) => `+${n} autres gagnants aujourd'hui, avec leurs pubs, boutiques, fournisseurs et marges`,
    seeAll: "Tout voir gratuitement", unlock: "Débloquer", pick: (n) => `Produit n°${n}`,
    freePick: "N°1 · PRODUIT GRATUIT DU JOUR", topPick: "Le produit n°1 du jour",
    stores: (n) => `${n} boutiques`, daysAds: (n) => `${n} jours de pub`,
  },
  footer: { privacy: "Confidentialité", terms: "Conditions", contact: "Contact" },
  trend: { emerging: "Émergent", growing: "En croissance", stable: "Stable", declining: "En baisse", spike: "Pic viral", seasonal: "Saisonnier", unknown: "Tendance floue" },
  radar: { demand: "Demande", profitability: "Marge", competition: "Concurr.", creative: "Créatif", differentiation: "Offre", logistics: "Logistique", market_fit: "Marché", risk: "Risque" },
};

export const LANDING_COPY: Record<Lang, LandingCopy> = { en: EN, fr: FR };
