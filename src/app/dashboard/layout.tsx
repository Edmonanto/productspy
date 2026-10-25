import Sidebar from "@/components/layout/Sidebar";
import TrialBanner from "@/components/layout/TrialBanner";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-zinc-950">
      <Sidebar />
      <main className="flex-1 min-w-0">
        <TrialBanner />
        {children}
      </main>
    </div>
  );
}
