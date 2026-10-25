import type { Metadata } from "next";
import LegalPage from "@/components/legal/LegalPage";
import { SITE } from "@/lib/site";

export const metadata: Metadata = { title: `Terms of Service — ${SITE.name}` };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service">
      <section>
        <p>
          These terms govern your use of {SITE.name} ({SITE.url}), operated by {SITE.company}. By creating an account
          you agree to them.
        </p>
      </section>
      <section>
        <h2>The service</h2>
        <p>
          {SITE.name} analyses publicly available ads and social media posts and suggests products that show signs of
          demand. Scores, prices, costs and margins are estimates based on that data.
        </p>
      </section>
      <section>
        <h2>No guarantee of results</h2>
        <p>
          A product appearing in Daily Winners is not a promise that it will sell or be profitable for you. You are
          responsible for your own business decisions, ad spend, product testing, and for checking that the products
          you sell are legal, safe and free of intellectual-property issues in your market.
        </p>
      </section>
      <section>
        <h2>Your account</h2>
        <ul>
          <li>Keep your login details private; you are responsible for activity on your account.</li>
          <li>One account per person. Don&apos;t share, resell or redistribute the picks or data in bulk.</li>
          <li>Don&apos;t try to scrape, overload or break the service.</li>
        </ul>
      </section>
      <section>
        <h2>Free trial, plans and billing</h2>
        <ul>
          <li>New accounts get a 7-day free trial of the Pro plan, with no card required. When it ends without a paid plan, the account moves to the Free plan.</li>
          <li>Paid plans are billed monthly in advance through Stripe and renew automatically until cancelled.</li>
          <li>You can cancel at any time from the Billing page; you keep access until the end of the period you paid for.</li>
          <li>We may change prices with at least 30 days&apos; notice by email.</li>
        </ul>
      </section>
      <section>
        <h2>Sourcing quotes</h2>
        <p>
          Quotes are estimates for your stated quantity and destination. An order is only confirmed once you accept a
          final written quote.
        </p>
      </section>
      <section>
        <h2>Third-party data and links</h2>
        <p>
          {SITE.name} is independent and not affiliated with or endorsed by Meta, TikTok, AliExpress or any store we
          link to. Their content belongs to them, and we are not responsible for external sites.
        </p>
      </section>
      <section>
        <h2>Liability</h2>
        <p>
          The service is provided &quot;as is&quot;. To the extent the law allows, our total liability for any claim is limited
          to the amount you paid us in the 3 months before it.
        </p>
      </section>
      <section>
        <h2>Ending your account</h2>
        <p>
          You can close your account at any time. We may suspend accounts that break these terms.
        </p>
      </section>
      <section>
        <h2>Changes and contact</h2>
        <p>
          We may update these terms and will tell you by email about significant changes. Questions:{" "}
          <a href={`mailto:${SITE.supportEmail}`}>{SITE.supportEmail}</a>.
        </p>
      </section>
    </LegalPage>
  );
}
