import Sidebar from "@/components/layout/Sidebar";
import TrialBanner from "@/components/layout/TrialBanner";
import AttachRef from "@/components/partners/AttachRef";
import SwrProvider from "@/components/layout/SwrProvider";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SwrProvider>
    <div className="flex min-h-screen bg-zinc-950">
      <Sidebar />
      <main className="flex-1 min-w-0">
        <AttachRef />
        <TrialBanner />
        {children}
      </main>
    </div>
    </SwrProvider>
  );
}
