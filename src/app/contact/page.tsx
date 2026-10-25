import type { Metadata } from "next";
import Link from "next/link";
import { Mail, FileText, CreditCard } from "lucide-react";
import LegalPage from "@/components/legal/LegalPage";
import { SITE } from "@/lib/site";

export const metadata: Metadata = { title: `Contact — ${SITE.name}` };

export default function ContactPage() {
  return (
    <LegalPage title="Contact us" showUpdated={false}>
      <p>We usually reply within one business day.</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 not-prose">
        <a href={`mailto:${SITE.supportEmail}`} className="!text-zinc-300 bg-zinc-900 border border-zinc-800 hover:border-violet-600/50 rounded-xl p-5 space-y-2 block">
          <Mail size={18} className="text-violet-400" />
          <div className="text-white font-semibold">Email</div>
          <div className="text-zinc-400 text-xs break-all">{SITE.supportEmail}</div>
        </a>
        <Link href="/dashboard/quotes" className="!text-zinc-300 bg-zinc-900 border border-zinc-800 hover:border-violet-600/50 rounded-xl p-5 space-y-2 block">
          <FileText size={18} className="text-violet-400" />
          <div className="text-white font-semibold">Sourcing quotes</div>
          <div className="text-zinc-400 text-xs">Request one from any product page; replies appear in Quotes.</div>
        </Link>
        <Link href="/dashboard/billing" className="!text-zinc-300 bg-zinc-900 border border-zinc-800 hover:border-violet-600/50 rounded-xl p-5 space-y-2 block">
          <CreditCard size={18} className="text-violet-400" />
          <div className="text-white font-semibold">Plans & billing</div>
          <div className="text-zinc-400 text-xs">Change or cancel your plan any time.</div>
        </Link>
      </div>
    </LegalPage>
  );
}
