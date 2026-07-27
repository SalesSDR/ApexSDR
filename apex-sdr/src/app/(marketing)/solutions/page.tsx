/* eslint-disable */
// @ts-nocheck
"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Target, Inbox, RotateCcw, Calendar, Users, TrendingUp, Zap, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { APP_URL } from "@/lib/config";

const useCases = [
  {
    icon: <Target size={24} />,
    title: "Outbound Cold Prospecting",
    description: "Scale multi-channel campaigns without hiring 40 BDRs. Apex SDR builds the lists, writes the copy, and handles the initial replies autonomously."
  },
  {
    icon: <Inbox size={24} />,
    title: "Inbound Lead Qualification",
    description: "Instantly research, qualify, and book meetings within seconds of form submit. Never lose a lead to slow response times again."
  },
  {
    icon: <RotateCcw size={24} />,
    title: "Lead Reactivation & Closed Lost",
    description: "Automatically re-engage dormant database leads and stale opportunities with highly contextual check-ins."
  },
  {
    icon: <Calendar size={24} />,
    title: "Event & Webinar Follow-Up",
    description: "Turn event registration lists into warm sales conversations. Apex SDR references specific event attendance to drive high conversion."
  }
];

const roles = [
  {
    id: "sdr",
    title: "For Sales Development (SDRs/BDRs)",
    heading: "Focus on closing, not copying and pasting.",
    description: "Eliminate 30+ hours of manual data entry, list building, and copy pasting. Apex SDR acts as your tireless assistant, teeing up warm replies for you to take over.",
    icon: <Users size={20} />
  },
  {
    id: "leadership",
    title: "For Sales Leadership & RevOps",
    heading: "Predictable pipeline without the headcount.",
    description: "Achieve 5x ROI, predictable pipeline, and total activity visibility in CRM. Scale your outbound motion infinitely without managing a massive team.",
    icon: <TrendingUp size={20} />
  },
  {
    id: "founders",
    title: "For Founders & Lean Teams",
    heading: "Enterprise-grade outbound on autopilot.",
    description: "Execute sophisticated outbound motions with zero headcount overhead. Focus on building your product while Apex SDR books your calendar.",
    icon: <Zap size={20} />
  }
];

export default function SolutionsPage() {
  const [activeRole, setActiveRole] = useState(roles[0].id);

  return (
    <div className="flex flex-col min-h-screen">
      {/* Hero Section */}
      <section className="relative pt-32 pb-24 overflow-hidden">
        {/* Background Gradients */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-5xl h-[600px] bg-gradient-to-b from-[#E5D5C5]/10 to-transparent rounded-full blur-[120px] pointer-events-none" />
        
        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="flex flex-col items-center text-center max-w-4xl mx-auto">
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="mb-8 inline-flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/5 backdrop-blur-sm"
            >
              <Sparkles size={14} className="text-[#E5D5C5]" />
              <span className="text-sm font-semibold tracking-wide uppercase text-gray-300">
                Tailored Outbound Motions
              </span>
            </motion.div>

            <motion.h1 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="text-5xl md:text-7xl font-bold tracking-tighter mb-8 text-transparent bg-clip-text bg-gradient-to-b from-white to-gray-400 leading-[1.1]"
            >
              Solutions Built for Every Sales Strategy
            </motion.h1>

            <motion.p 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="text-xl md:text-2xl text-gray-400 mb-12 leading-relaxed"
            >
              Whether you're executing outbound prospecting, inbound lead qualification, or event follow-ups, Apex SDR automates your revenue growth.
            </motion.p>
          </div>
        </div>
      </section>

      {/* Solutions by Use Case (Grid) */}
      <section className="py-24 bg-black relative border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-16">
            <h2 className="text-3xl md:text-5xl font-bold tracking-tighter text-white mb-6">
              Use Cases
            </h2>
            <p className="text-xl text-gray-400 max-w-2xl">
              Apex SDR seamlessly adapts to your specific go-to-market strategy.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {useCases.map((useCase, idx) => (
              <div 
                key={idx} 
                className="bg-[#0a0a0a] border border-white/10 p-10 rounded-3xl hover:bg-[#111] transition-all group overflow-hidden relative"
              >
                <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity transform group-hover:scale-110 duration-500">
                  {useCase.icon}
                </div>
                <div className="w-14 h-14 rounded-2xl bg-[#E5D5C5]/10 flex items-center justify-center text-[#E5D5C5] mb-8 relative z-10">
                  {useCase.icon}
                </div>
                <h3 className="text-2xl font-bold text-white mb-4 relative z-10">{useCase.title}</h3>
                <p className="text-gray-400 text-lg leading-relaxed relative z-10">{useCase.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Solutions by Role (Tabs Component) */}
      <section className="py-24 bg-[#050505] relative border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-bold tracking-tighter text-white mb-6">
              Built for the Entire Revenue Team
            </h2>
          </div>

          <div className="flex flex-col items-center">
            {/* Tab Triggers */}
            <div className="flex flex-wrap justify-center gap-2 mb-12 p-2 bg-white/5 rounded-full border border-white/10 backdrop-blur-sm">
              {roles.map((role) => (
                <button
                  key={role.id}
                  onClick={() => setActiveRole(role.id)}
                  className={cn(
                    "px-6 py-3 rounded-full text-sm font-semibold transition-all flex items-center gap-2 relative",
                    activeRole === role.id ? "text-black" : "text-gray-400 hover:text-white"
                  )}
                >
                  {activeRole === role.id && (
                    <motion.div
                      layoutId="roleTab"
                      className="absolute inset-0 bg-[#E5D5C5] rounded-full"
                      transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                    />
                  )}
                  <span className="relative z-10 flex items-center gap-2">
                    {role.icon} {role.title}
                  </span>
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="w-full max-w-4xl relative min-h-[300px]">
              <AnimatePresence mode="wait">
                {roles.map((role) => role.id === activeRole && (
                  <motion.div
                    key={role.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    transition={{ duration: 0.4 }}
                    className="absolute inset-0 bg-black border border-white/10 rounded-3xl p-10 md:p-16 flex flex-col items-center text-center shadow-2xl"
                  >
                    <h3 className="text-3xl md:text-4xl font-bold text-white mb-6 leading-tight">
                      {role.heading}
                    </h3>
                    <p className="text-xl text-gray-400 leading-relaxed max-w-2xl">
                      {role.description}
                    </p>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </section>

      {/* Customer Outcomes / Metrics Cards */}
      <section className="py-32 bg-black relative border-t border-white/5 overflow-hidden">
        {/* Decorative Grid */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none" />
        
        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="mb-16">
            <h2 className="text-3xl md:text-5xl font-bold tracking-tighter text-white mb-6">
              Proven Outcomes
            </h2>
            <p className="text-xl text-gray-400 max-w-2xl">
              Don't just take our word for it. See the real numbers driven by our digital workforce.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Card 1 */}
            <div className="bg-[#111] border border-white/10 p-10 rounded-3xl flex flex-col justify-between h-[300px] hover:border-[#E5D5C5]/30 transition-colors group">
              <div>
                <p className="text-gray-400 font-medium mb-4 uppercase tracking-widest text-xs">Pipeline</p>
                <h3 className="text-4xl lg:text-5xl font-bold text-white leading-tight">
                  $1M+
                </h3>
              </div>
              <p className="text-xl text-gray-300 font-medium group-hover:text-[#E5D5C5] transition-colors">
                Pipeline Generated in First 3 Months
              </p>
            </div>

            {/* Card 2 */}
            <div className="bg-[#111] border border-white/10 p-10 rounded-3xl flex flex-col justify-between h-[300px] hover:border-[#E5D5C5]/30 transition-colors group">
              <div>
                <p className="text-gray-400 font-medium mb-4 uppercase tracking-widest text-xs">Efficiency</p>
                <h3 className="text-4xl lg:text-5xl font-bold text-white leading-tight">
                  2,000<span className="text-2xl text-gray-500 ml-1">hrs</span>
                </h3>
              </div>
              <p className="text-xl text-gray-300 font-medium group-hover:text-[#E5D5C5] transition-colors">
                Of Manual Work Automated per Month
              </p>
            </div>

            {/* Card 3 */}
            <div className="bg-[#111] border border-white/10 p-10 rounded-3xl flex flex-col justify-between h-[300px] hover:border-[#E5D5C5]/30 transition-colors group">
              <div>
                <p className="text-gray-400 font-medium mb-4 uppercase tracking-widest text-xs">Engagement</p>
                <h3 className="text-4xl lg:text-5xl font-bold text-white leading-tight">
                  9.7%
                </h3>
              </div>
              <p className="text-xl text-gray-300 font-medium group-hover:text-[#E5D5C5] transition-colors">
                Positive Reply Rate Across Email & LinkedIn
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Final Call to Action */}
      <section className="py-32 relative overflow-hidden bg-[#0a0a0a] border-t border-white/10">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full max-w-4xl bg-[#E5D5C5]/5 rounded-full blur-[150px] pointer-events-none" />
        <div className="max-w-4xl mx-auto px-6 relative z-10 text-center flex flex-col items-center">
          <h2 className="text-4xl md:text-6xl font-bold tracking-tighter text-white mb-8 leading-tight">
            Transform Your Outbound Pipeline Now
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
