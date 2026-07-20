import { Metadata } from "next";
import { MarketingHeader } from "@/components/marketing/MarketingHeader";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";
import { AskApexWidget } from "@/components/marketing/AskApexWidget";

export const metadata: Metadata = {
  title: "Apex SDR | Autonomous AI Growth & Sales Platform",
};

export default function MarketingLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="min-h-screen bg-black text-white font-sans selection:bg-[#E5D5C5] selection:text-black">
      <MarketingHeader />
      <main>
        {children}
      </main>
      <MarketingFooter />
      <AskApexWidget />
    </div>
  );
}
