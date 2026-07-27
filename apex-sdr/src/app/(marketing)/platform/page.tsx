"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Bot, Shield, Database, Zap, Search, Mail, Lock, Server, CheckCircle2, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import { APP_URL } from "@/lib/config";

const pillars = [
  {
    id: "prospecting",
    title: "Autonomous Prospecting & ICP Engine",
    icon: <Search size={20} />,
    description: "Filters 400M+ contacts, evaluates fit over simple filter-matching, performs live web searches, and tracks intent signals like funding rounds, job changes, and tech stack adoption.",
    features: ["400M+ Verified Contacts", "Live Web Search", "Intent Signal Tracking"],
  },
  {
    id: "research",
    title: "Deep Account Research & Hyper-Personalization",
    icon: <Bot size={20} />,
    description: "AI conducts 1-on-1 account research by reading news, SEC filings, and tech stacks to draft unique 1-to-1 personalized emails—no generic templates ever.",
    features: ["SEC & News Analysis", "No Generic Templates", "1-to-1 Personalization"],
  },
  {
    id: "execution",
    title: "Multi-Channel Execution Engine",
    icon: <Zap size={20} />,
    description: "Cascading outreach across LinkedIn invitations, email sequences, and phone calls using intelligent, automated fallback logic.",
    features: ["LinkedIn & Email", "Automated Fallbacks", "Dynamic Sequencing"],
  },
  {
    id: "safety",
    title: "Real-Time Safety & Webhook Interception",
    icon: <Shield size={20} />,
    description: "Instant reply detection and intent classification that automatically halts automated sequences the second a human responds to protect brand reputation.",
    features: ["Instant Reply Detection", "Intent Classification", "Brand Protection"],
  }
];

export default function PlatformPage() {
  const [activePillar, setActivePillar] = useState(pillars[0].id);

  return (
    <div className="flex flex-col min-h-screen">
      {/* Hero Section */}
      <section className="relative pt-32 pb-24 overflow-hidden">
        {/* Background Gradients */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-4xl h-[500px] bg-gradient-to-b from-[#E5D5C5]/10 to-transparent rounded-full blur-[120px] pointer-events-none" />
        
        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="flex flex-col items-center text-center max-w-4xl mx-auto">
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="mb-8 inline-flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/5 backdrop-blur-sm"
            >
              <Activity size={14} className="text-[#E5D5C5]" />
              <span className="text-sm font-semibold tracking-wide uppercase text-gray-300">
                The Autonomous SDR Infrastructure
              </span>
            </motion.div>

            <motion.h1 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="text-5xl md:text-7xl font-bold tracking-tighter mb-8 text-transparent bg-clip-text bg-gradient-to-b from-white to-gray-400 leading-[1.1]"
            >
              A Multi-Agent Engine Built for Unstoppable Outbound
            </motion.h1>

            <motion.p 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="text-xl md:text-2xl text-gray-400 mb-12 leading-relaxed"
            >
              Apex SDR replaces manual list-building, research, and repetitive sequencing with autonomous AI digital workers operating 24/7.
            </motion.p>

            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="flex flex-col sm:flex-row items-center gap-4"
            >
              <Link 
                href="/demo"
                className="w-full sm:w-auto flex items-center justify-center gap-2 bg-white text-black px-8 py-4 rounded-full font-bold text-lg hover:bg-gray-200 transition-all"
              >
                Book a Live Demo <ArrowRight size={18} />
              </Link>
              <Link 
                href="/solutions" 
                className="w-full sm:w-auto flex items-center justify-center gap-2 bg-transparent text-white border border-white/20 px-8 py-4 rounded-full font-bold text-lg hover:bg-white/5 transition-all"
              >
                Explore Solutions
              </Link>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Core Capability Pillars */}
      <section className="py-24 bg-black relative border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-16">
            <h2 className="text-3xl md:text-5xl font-bold tracking-tighter text-white mb-6">
              Core Capabilities
            </h2>
            <p className="text-xl text-gray-400 max-w-2xl">
              Everything you need to automate your entire outbound motion, built directly into the core platform.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
            {/* Tabs List */}
            <div className="lg:col-span-5 flex flex-col gap-2">
              {pillars.map((pillar) => {
                const isActive = activePillar === pillar.id;
                return (
                  <button
                    key={pillar.id}
                    onClick={() => setActivePillar(pillar.id)}
                    className={cn(
                      "flex items-center gap-4 p-6 rounded-2xl text-left transition-all duration-300 relative overflow-hidden group border",
                      isActive 
                        ? "bg-white/5 border-white/20" 
                        : "bg-transparent border-transparent hover:bg-white/5 hover:border-white/10"
                    )}
                  >
                    {isActive && (
                      <motion.div 
                        layoutId="activePillar"
                        className="absolute left-0 top-0 w-1 h-full bg-[#E5D5C5]"
                      />
                    )}
                    <div className={cn(
                      "p-3 rounded-lg transition-colors",
                      isActive ? "bg-[#E5D5C5] text-black" : "bg-white/10 text-gray-400 group-hover:text-white"
                    )}>
                      {pillar.icon}
                    </div>
                    <span className={cn(
                      "font-semibold text-lg transition-colors",
                      isActive ? "text-white" : "text-gray-400 group-hover:text-white"
                    )}>
                      {pillar.title}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Tab Content */}
            <div className="lg:col-span-7">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activePillar}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.3 }}
                  className="bg-[#0c0c0c] border border-white/10 p-8 md:p-12 rounded-3xl h-full flex flex-col justify-center relative overflow-hidden"
                >
                  <div className="absolute top-0 right-0 w-64 h-64 bg-[#E5D5C5]/5 rounded-full blur-[80px]" />
                  
                  {pillars.map((pillar) => pillar.id === activePillar && (
                    <div key={pillar.id} className="relative z-10">
                      <div className="w-14 h-14 rounded-2xl bg-[#E5D5C5]/10 flex items-center justify-center text-[#E5D5C5] mb-8">
                        {pillar.icon}
                      </div>
                      <h3 className="text-3xl font-bold text-white mb-6 leading-tight">
                        {pillar.title}
                      </h3>
                      <p className="text-xl text-gray-400 leading-relaxed mb-10">
                        {pillar.description}
                      </p>
                      
                      <ul className="flex flex-col gap-4">
                        {pillar.features.map((feature, idx) => (
                          <li key={idx} className="flex items-center gap-3 text-white font-medium">
                            <CheckCircle2 size={20} className="text-[#E5D5C5]" />
                            {feature}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>
      </section>

      {/* Interactive Architecture Section */}
      <section className="py-24 bg-[#050505] relative border-t border-white/5 overflow-hidden">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-bold tracking-tighter text-white mb-6">
              Platform Architecture
            </h2>
            <p className="text-xl text-gray-400 max-w-3xl mx-auto">
              A robust, decoupled architecture separating the control plane from heavy execution layers.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-5xl mx-auto">
            {/* Control Plane */}
            <div className="bg-black border border-white/10 rounded-3xl p-8 flex flex-col items-center text-center relative overflow-hidden group hover:border-[#E5D5C5]/30 transition-colors">
              <div className="absolute inset-0 bg-gradient-to-b from-[#E5D5C5]/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-6 relative z-10 border border-white/10">
                <Server className="text-white" size={28} />
              </div>
              <h3 className="text-2xl font-bold text-white mb-4 relative z-10">Control Plane</h3>
              <p className="text-gray-400 mb-8 relative z-10">
                The centralized brain managing users, billing, and campaign logic.
              </p>
              <div className="flex flex-wrap justify-center gap-3 relative z-10">
                <span className="px-4 py-2 rounded-full bg-white/5 text-sm font-medium border border-white/10">FastAPI</span>
                <span className="px-4 py-2 rounded-full bg-white/5 text-sm font-medium border border-white/10">Next.js UI</span>
                <span className="px-4 py-2 rounded-full bg-white/5 text-sm font-medium border border-white/10">Postgres</span>
              </div>
            </div>

            {/* Execution Plane */}
            <div className="bg-black border border-white/10 rounded-3xl p-8 flex flex-col items-center text-center relative overflow-hidden group hover:border-[#E5D5C5]/30 transition-colors">
              <div className="absolute inset-0 bg-gradient-to-b from-[#E5D5C5]/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-6 relative z-10 border border-white/10">
                <Database className="text-white" size={28} />
              </div>
              <h3 className="text-2xl font-bold text-white mb-4 relative z-10">Execution Plane</h3>
              <p className="text-gray-400 mb-8 relative z-10">
                Distributed workers handling heavy data processing and API integrations.
              </p>
              <div className="flex flex-wrap justify-center gap-3 relative z-10">
                <span className="px-4 py-2 rounded-full bg-white/5 text-sm font-medium border border-white/10">ARQ Workers</span>
                <span className="px-4 py-2 rounded-full bg-white/5 text-sm font-medium border border-white/10">Redis</span>
                <span className="px-4 py-2 rounded-full bg-white/5 text-sm font-medium border border-white/10">Unipile / Apollo</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Enterprise-Ready & Security Grid */}
      <section className="py-24 bg-black relative border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-16">
            <h2 className="text-3xl md:text-5xl font-bold tracking-tighter text-white mb-6">
              Enterprise Grade Security
            </h2>
            <p className="text-xl text-gray-400 max-w-2xl">
              Built from day one to protect your data, your sender reputation, and your brand.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              {
                icon: <Lock size={24} />,
                title: "SOC-2 Type II",
                desc: "Bank-level encryption and strict access controls across all infrastructure."
              },
              {
                icon: <Database size={24} />,
                title: "Row-Level Security",
                desc: "Strict multi-tenancy ensures your prospect data is fully isolated."
              },
              {
                icon: <Shield size={24} />,
                title: "Rate-Limiting Guards",
                desc: "Automated daily limits to protect accounts from blocks or suspension."
              },
              {
                icon: <Mail size={24} />,
                title: "Deliverability Engine",
                desc: "Built-in inbox rotation and domain warming protects sender rep."
              }
            ].map((item, i) => (
              <div key={i} className="p-8 rounded-3xl bg-[#0a0a0a] border border-white/10 hover:bg-[#111] transition-colors">
                <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center text-[#E5D5C5] mb-6">
                  {item.icon}
                </div>
                <h4 className="text-xl font-bold text-white mb-3">{item.title}</h4>
                <p className="text-gray-400 text-sm leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="py-32 relative overflow-hidden bg-black border-t border-white/10">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(229,213,197,0.1),transparent_50%)]" />
        <div className="max-w-4xl mx-auto px-6 relative z-10 text-center flex flex-col items-center">
          <h2 className="text-4xl md:text-6xl font-bold tracking-tighter text-white mb-8 leading-tight">
            Deploy Your Digital SDR Workforce Today
          </h2>
          <Link 
            href="/demo"
            className="flex items-center justify-center gap-2 bg-[#E5D5C5] text-black px-10 py-5 rounded-full font-bold text-xl hover:bg-white transition-all shadow-[0_0_40px_rgba(229,213,197,0.3)] hover:shadow-[0_0_60px_rgba(255,255,255,0.4)]"
          >
            Book a Live Demo <ArrowRight size={20} />
          </Link>
        </div>
      </section>
    </div>
  );
}
