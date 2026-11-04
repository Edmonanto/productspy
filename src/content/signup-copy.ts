/** Signup page copy, English and French (French via /signup?lang=fr). */
import type { Lang } from "@/content/landing-copy";

export interface SignupCopy {
  title: string; subtitle: string;
  trialTitle: string; perks: string[]; trialNote: string;
  google: string; or: string;
  name: string; namePlaceholder: string; email: string; emailPlaceholder: string;
  password: string; passwordPlaceholder: string; show: string; hide: string;
  strength: [string, string, string]; rules: { length: string; upper: string; number: string };
  tooWeak: string; submit: string;
  agree: [string, string, string, string];   // "By signing up, you agree to our", Terms, "and", Privacy Policy
  haveAccount: string; signIn: string;
  check: { title: string; sent: string; next: string; steps: string[]; wrong: string; back: string };
  /** Supabase error messages we know, translated. Unknown ones are shown as-is. */
  errors: Record<string, string>;
}

const EN: SignupCopy = {
  title: "Create your account", subtitle: "Start finding winning products today",
  trialTitle: "7 days of Pro free — no card needed",
  perks: [
    "Daily Winners: 5–10 products being scaled right now",
    "3 markets — United States, United Kingdom, France",
    "The ads, stores and margins behind each pick",
  ],
  trialNote: "After 7 days you move to the Free plan automatically unless you choose a plan.",
  google: "Continue with Google", or: "or",
  name: "Full name", namePlaceholder: "John Doe", email: "Email", emailPlaceholder: "you@example.com",
  password: "Password", passwordPlaceholder: "Min. 8 characters", show: "Show password", hide: "Hide password",
  strength: ["Weak", "Fair", "Strong"], rules: { length: "8+ chars", upper: "Uppercase", number: "Number" },
  tooWeak: "Password is too weak. Add uppercase letters or numbers.",
  submit: "Create account",
  agree: ["By signing up, you agree to our", "Terms", "and", "Privacy Policy"],
  haveAccount: "Already have an account?", signIn: "Sign in",
  check: {
    title: "Check your email", sent: "We sent a confirmation link to", next: "Next steps:",
    steps: ["Open the email from ProductSpy Pro", "Click the confirmation link", "You'll be redirected to your dashboard"],
    wrong: "Wrong email?", back: "Go back",
  },
  errors: {},
};

const FR: SignupCopy = {
  title: "Crée ton compte", subtitle: "Commence à trouver des produits gagnants dès aujourd'hui",
  trialTitle: "7 jours de Pro offerts — sans carte bancaire",
  perks: [
    "Les gagnants du jour : 5 à 10 produits en train d'être scalés",
    "3 marchés — France, Royaume-Uni, États-Unis",
    "Les pubs, boutiques et marges derrière chaque produit",
  ],
  trialNote: "Après 7 jours, tu passes automatiquement sur l'offre Free, sauf si tu choisis une offre.",
  google: "Continuer avec Google", or: "ou",
  name: "Nom complet", namePlaceholder: "Marie Dupont", email: "E-mail", emailPlaceholder: "toi@exemple.fr",
  password: "Mot de passe", passwordPlaceholder: "8 caractères minimum", show: "Afficher le mot de passe", hide: "Masquer le mot de passe",
  strength: ["Faible", "Moyen", "Fort"], rules: { length: "8+ caractères", upper: "Majuscule", number: "Chiffre" },
  tooWeak: "Mot de passe trop faible. Ajoute des majuscules ou des chiffres.",
  submit: "Créer mon compte",
  agree: ["En t'inscrivant, tu acceptes nos", "Conditions", "et notre", "Politique de confidentialité"],
  haveAccount: "Tu as déjà un compte ?", signIn: "Connexion",
  check: {
    title: "Vérifie tes e-mails", sent: "On a envoyé un lien de confirmation à", next: "Étapes suivantes :",
    steps: ["Ouvre l'e-mail de ProductSpy Pro", "Clique sur le lien de confirmation", "Tu arrives directement sur ton tableau de bord"],
    wrong: "Mauvaise adresse ?", back: "Revenir en arrière",
  },
  errors: {
    "User already registered": "Un compte existe déjà avec cette adresse. Connecte-toi plutôt.",
    "Unable to validate email address: invalid format": "Cette adresse e-mail n'est pas valide.",
    "Password should be at least 6 characters.": "Le mot de passe doit faire au moins 6 caractères.",
    "Email rate limit exceeded": "Trop de tentatives. Réessaie dans quelques minutes.",
    "email rate limit exceeded": "Trop de tentatives. Réessaie dans quelques minutes.",
  },
};

export const SIGNUP_COPY: Record<Lang, SignupCopy> = { en: EN, fr: FR };
