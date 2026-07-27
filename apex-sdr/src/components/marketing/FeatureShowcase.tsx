/* eslint-disable */
// @ts-nocheck
"use client";

import { motion } from "framer-motion";
import { Database, Mail, Phone, Bot, Workflow, BarChart3 } from "lucide-react";

export function FeatureShowcase() {
  const features = [
    {
      title: "Conversational ICP Builder",
      description: "Define your ideal customer profile using natural language. Apex parses it into structured filters instantly.",
      icon: <Bot size={24} className="text-[#E5D5C5]" />,
    },
    {
      title: "Real-time Enrichment",
      description: "Automatically enriches leads with accurate email addresses and phone numbers via Apollo integration.",
      icon: <Database size={24} className="text-[#E5D5C5]" />,
    },
    {
      title: "Multi-channel Outreach",
      description: "Orchestrates highly personalized touchpoints across LinkedIn, Email, and Voice simultaneously.",
      icon: <Mail size={24} className="text-[#E5D5C5]" />,
    },
    {
      title: "Autonomous State Machine",
      description: "Background workers automatically advance prospects through sequence steps without human intervention.",
      icon: <Workflow size={24} className="text-[#E5D5C5]" />,
    },
    {
      title: "Intent Classification",
      description: "Analyzes inbound replies to detect sentiment (Positive, Negative, Not Interested) and halts sequences.",
      icon: <BarChart3 size={24} className="text-[#E5D5C5]" />,
    },
    {
      title: "Voice Calling Integration",
      description: "Directly trigger and log calls with prospects using Twilio right from the active queue.",
      icon: <Phone size={24} className="text-[#E5D5C5]" />,
    },
  ];

  return (
    <section className="py-24 bg-black relative">
      <div className="max-w-7xl mx-auto px-6 relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-3xl md:text-5xl font-bold text-white tracking-tight">
            An entire sales team, <br/> built into one agent.
          </h2>
          <p className="mt-6 text-gray-400 text-lg">
            Apex SDR doesn't just give you tools—it executes the work for you. Discover the intelligent features powering the next generation of sales.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: idx * 0.1 }}
              className="p-8 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors group"
            >
              <div className="w-12 h-12 rounded-full bg-black flex items-center justify-center mb-6 border border-white/5 group-hover:scale-110 transition-transform">
                {feature.icon}
              </div>
              <h3 className="text-xl font-bold text-white mb-3">{feature.title}</h3>
              <p className="text-gray-400 leading-relaxed">
                {feature.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
