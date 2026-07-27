import { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, CheckCircle2 } from "lucide-react";

export const metadata: Metadata = {
  title: "Apex SDR Product | Autonomous Sales Agent",
};

export default function ApexSDRProductPage() {
  return (
    <div className="pt-32 pb-24 max-w-7xl mx-auto px-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
        <div>
          <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight mb-6">
            Meet <span className="text-[#E5D5C5]">Apex.</span>
          </h1>
          <p className="text-xl text-gray-400 leading-relaxed mb-8">
            The first AI agent that actually acts like a senior SDR. Connect your LinkedIn, define your ICP in plain English, and watch Apex build lists, write emails, and book meetings autonomously.
          </p>
          
          <div className="flex flex-col gap-4 mb-10">
            {["Natural language ICP parsing", "Real-time Apollo enrichment", "Multi-channel sequences", "AI intent classification"].map(feature => (
              <div key={feature} className="flex items-center gap-3">
                <CheckCircle2 size={20} className="text-[#E5D5C5]" />
                <span className="text-lg text-gray-300">{feature}</span>
              </div>
            ))}
          </div>

          <Link
            href="/demo"
            className="inline-flex items-center gap-2 px-8 py-4 rounded-full bg-[#E5D5C5] text-black font-bold text-lg hover:bg-white transition-colors"
          >
            Book a Live Demo <ArrowRight size={20} />
          </Link>
        </div>

        <div className="relative">
          {/* Mockup Dashboard Graphic */}
          <div className="aspect-[4/3] rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md overflow-hidden relative shadow-2xl">
            <div className="absolute top-0 left-0 right-0 h-12 bg-black/40 border-b border-white/5 flex items-center px-4 gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500/50" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/50" />
              <div className="w-3 h-3 rounded-full bg-green-500/50" />
            </div>
            <div className="p-8 pt-20">
              <div className="h-8 w-1/3 bg-white/10 rounded mb-6" />
              <div className="space-y-4">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="h-16 w-full bg-white/5 rounded-lg flex items-center px-4 gap-4">
                    <div className="w-10 h-10 rounded-full bg-white/10" />
                    <div className="flex-1 space-y-2">
                      <div className="h-3 w-1/4 bg-white/10 rounded" />
                      <div className="h-2 w-1/2 bg-white/5 rounded" />
                    </div>
                    <div className="h-6 w-24 bg-[#E5D5C5]/20 rounded-full" />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="absolute -z-10 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-[#E5D5C5]/10 blur-[100px] rounded-full pointer-events-none" />
        </div>
      </div>
    </div>
  );
}
