/**
 * OAuth + email confirmation callback handler.
 * Supabase redirects here after Google OAuth or email link click.
 */
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/dashboard";
  const error = searchParams.get("error");
  const errorDescription = searchParams.get("error_description");

  // Handle OAuth error
  if (error) {
    console.error(`[Auth Callback] ${error}: ${errorDescription}`);
    return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent(errorDescription ?? error)}`);
  }

  if (code) {
    const supabase = await createClient();
    const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);

    if (!exchangeError) {
      return NextResponse.redirect(`${origin}${next}`);
    }

    console.error("[Auth Callback] Code exchange error:", exchangeError);
  }

  return NextResponse.redirect(`${origin}/login?error=Authentication+failed`);
}
