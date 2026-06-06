"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { Zap, Eye, EyeOff, AlertCircle, CheckCircle, Check } from "lucide-react";

const PLANS = [
  { id: "free", name: "Free", price: "$0/mo", features: ["5 searches/day", "Basic score"] },
  { id: "starter", name: "Starter", price: "$29/mo", features: ["50 searches/day", "Email alerts"] },
  { id: "pro", name: "Pro", price: "$79/mo", features: ["Unlimited", "Full AI + Ad spy"], popular: true },
];

export default function SignupPage() {
  const { signUp, signInWithGoogle } = useAuth();
  const [step, setStep] = useState<1 | 2>(1); // step 1 = form, step 2 = check email
  const [selectedPlan, setSelectedPlan] = useState("free");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Password strength
  const strength = {
    length: password.length >= 8,
    upper: /[A-Z]/.test(password),
    number: /[0-9]/.test(password),
  };
  const strengthScore = Object.values(strength).filter(Boolean).length;
  const strengthLabel = ["Weak", "Fair", "Strong"][strengthScore - 1] ?? "";
  const strengthColor = ["bg-red-500", "bg-yellow-500", "bg-emerald-500"][strengthScore - 1] ?? "bg-zinc-700";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (strengthScore < 2) {
      setError("Password is too weak. Add uppercase letters or numbers.");
      return;
    }
    setLoading(true);
    const { error } = await signUp(email, password, name);
    if (error) {
      setError(error);
      setLoading(false);
    } else {
      setStep(2);
    }
  };

  const handleGoogle = async () => {
    setGoogleLoading(true);
    await signInWithGoogle();
    setGoogleLoading(false);
  };

  // Step 2: Email confirm
  if (step === 2) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center space-y-6">
          <div className="w-16 h-16 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center mx-auto">
            <CheckCircle size={32} className="text-emerald-400" />
          </div>
          <div>
            <h1 className="text-white font-bold text-2xl">Check your email</h1>
            <p className="text-zinc-400 text-sm mt-2">
              We sent a confirmation link to{" "}
              <span className="text-white font-medium">{email}</span>
            </p>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 text-left space-y-3">
            <p className="text-zinc-400 text-sm">Next steps:</p>
            {[
              "Open the email from ProductSpy AI",
              "Click the confirmation link",
              "You'll be redirected to your dashboard",
            ].map((step, i) => (
              <div key={i} className="flex items-center gap-3 text-sm text-zinc-300">
                <div className="w-5 h-5 rounded-full bg-violet-600/20 border border-violet-600/30 text-violet-400 flex items-center justify-center text-xs font-bold shrink-0">
                  {i + 1}
                </div>
                {step}
              </div>
            ))}
          </div>
          <p className="text-zinc-600 text-sm">
            Wrong email?{" "}
            <button onClick={() => setStep(1)} className="text-violet-400 hover:text-violet-300 transition-colors">
              Go back
            </button>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-8">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-600 flex items-center justify-center">
            <Zap size={20} className="text-white" />
          </div>
          <div className="text-center">
            <h1 className="text-white font-bold text-2xl">Create your account</h1>
            <p className="text-zinc-500 text-sm mt-1">Start finding winning products today</p>
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-5">
          {/* Plan selector */}
          <div>
            <p className="text-zinc-400 text-xs font-medium mb-3">Choose a plan</p>
            <div className="grid grid-cols-3 gap-2">
              {PLANS.map((plan) => (
                <button
                  key={plan.id}
                  onClick={() => setSelectedPlan(plan.id)}
                  className={`relative p-3 rounded-xl border text-left transition-all text-xs
                    ${selectedPlan === plan.id
                      ? "border-violet-500 bg-violet-600/10"
                      : "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
                    }`}
                >
                  {plan.popular && (
                    <span className="absolute -top-2 left-1/2 -translate-x-1/2 bg-violet-600 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap">
                      POPULAR
                    </span>
                  )}
                  <p className={`font-bold ${selectedPlan === plan.id ? "text-violet-300" : "text-white"}`}>
                    {plan.name}
                  </p>
                  <p className="text-zinc-500 mt-0.5">{plan.price}</p>
                  <ul className="mt-2 space-y-1">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-start gap-1 text-zinc-400">
                        <Check size={9} className="text-emerald-400 mt-0.5 shrink-0" />
                        <span className="text-[10px] leading-tight">{f}</span>
                      </li>
                    ))}
                  </ul>
                </button>
              ))}
            </div>
          </div>

          {/* Google OAuth */}
          <button
            onClick={handleGoogle}
            disabled={googleLoading}
            className="w-full flex items-center justify-center gap-3 bg-white hover:bg-zinc-100 text-zinc-900 font-medium py-2.5 px-4 rounded-xl text-sm transition-colors disabled:opacity-60"
          >
            {googleLoading ? (
              <span className="w-4 h-4 border-2 border-zinc-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg viewBox="0 0 24 24" className="w-4 h-4">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
            )}
            Continue with Google
          </button>

          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-zinc-800" />
            <span className="text-zinc-600 text-xs">or</span>
            <div className="flex-1 h-px bg-zinc-800" />
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-xl">
              <AlertCircle size={14} className="shrink-0" />
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-zinc-400 text-xs font-medium">Full name</label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="John Doe"
                className="w-full bg-zinc-800 border border-zinc-700 text-white placeholder-zinc-600 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-zinc-400 text-xs font-medium">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full bg-zinc-800 border border-zinc-700 text-white placeholder-zinc-600 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-zinc-400 text-xs font-medium">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min. 8 characters"
                  className="w-full bg-zinc-800 border border-zinc-700 text-white placeholder-zinc-600 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-violet-500 transition-colors pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>

              {/* Password strength */}
              {password && (
                <div className="space-y-1.5">
                  <div className="flex gap-1">
                    {[0, 1, 2].map((i) => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition-colors ${
                          i < strengthScore ? strengthColor : "bg-zinc-700"
                        }`}
                      />
                    ))}
                  </div>
                  <div className="flex gap-3 text-xs">
                    {[
                      { key: "length", label: "8+ chars" },
                      { key: "upper", label: "Uppercase" },
                      { key: "number", label: "Number" },
                    ].map(({ key, label }) => (
                      <span
                        key={key}
                        className={strength[key as keyof typeof strength] ? "text-emerald-400" : "text-zinc-600"}
                      >
                        ✓ {label}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-violet-600 hover:bg-violet-500 disabled:bg-violet-800 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-xl text-sm transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : "Create account"}
            </button>
          </form>

          <p className="text-zinc-600 text-xs text-center">
            By signing up, you agree to our{" "}
            <a href="#" className="text-zinc-400 hover:text-white underline">Terms</a>{" "}
            and{" "}
            <a href="#" className="text-zinc-400 hover:text-white underline">Privacy Policy</a>
          </p>
        </div>

        <p className="text-center text-zinc-600 text-sm">
          Already have an account?{" "}
          <Link href="/login" className="text-violet-400 hover:text-violet-300 font-medium transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
