import type { Metadata } from "next";
import LegalPage from "@/components/legal/LegalPage";
import { SITE } from "@/lib/site";

export const metadata: Metadata = { title: `Privacy Policy — ${SITE.name}` };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy">
      <section>
        <p>
          This policy explains what {SITE.name} ({SITE.url}), operated by {SITE.company}, collects when you use the
          service, why, and what you can do about it.
        </p>
      </section>
      <section>
        <h2>What we collect</h2>
        <ul>
          <li><strong>Account details</strong> — your name, email address and, if you sign in with Google, your Google profile name and email.</li>
          <li><strong>Your settings and activity</strong> — the markets you follow, products you save to your watchlist, and sourcing quote requests (destination country, quantity, target price and notes).</li>
          <li><strong>Billing</strong> — your plan and subscription status. Card details are entered on and handled by Stripe; we never see or store your full card number.</li>
          <li><strong>Technical data</strong> — standard server logs (IP address, browser, pages requested) kept for security and troubleshooting.</li>
        </ul>
      </section>
      <section>
        <h2>How we use it</h2>
        <ul>
          <li>To run your account, show your Daily Winners and keep your watchlist and quotes.</li>
          <li>To manage your free trial and subscription, and to send service emails such as trial reminders and quote replies.</li>
          <li>To keep the service secure and fix problems.</li>
        </ul>
        <p className="mt-2">We do not sell your personal data and we do not use it for third-party advertising.</p>
      </section>
      <section>
        <h2>Service providers</h2>
        <p>We rely on these companies to run the service, each only for its part:</p>
        <ul>
          <li>Supabase — sign-in and database</li>
          <li>Vercel and Render — hosting</li>
          <li>Stripe — payments</li>
          <li>Resend — service emails</li>
        </ul>
      </section>
      <section>
        <h2>Product data</h2>
        <p>
          The products we show are built from publicly available ad libraries, public social media posts and public
          store and supplier pages. These sources contain information about products and advertisers, not about you.
        </p>
      </section>
      <section>
        <h2>Cookies and local storage</h2>
        <p>
          We use only what the service needs: a sign-in cookie to keep you logged in and your browser&apos;s local
          storage to remember your selected market. No advertising or tracking cookies.
        </p>
      </section>
      <section>
        <h2>Keeping and deleting your data</h2>
        <p>
          We keep your data while your account is open. You can ask us to export or delete your account and its data
          at any time by emailing <a href={`mailto:${SITE.supportEmail}`}>{SITE.supportEmail}</a>.
        </p>
      </section>
      <section>
        <h2>Contact</h2>
        <p>Questions about this policy: <a href={`mailto:${SITE.supportEmail}`}>{SITE.supportEmail}</a>.</p>
      </section>
    </LegalPage>
  );
}
