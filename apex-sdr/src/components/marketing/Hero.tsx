"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Bot, Target, Zap } from "lucide-react";

export function Hero() {
  return (
    <section className="relative pt-32 pb-20 overflow-hidden">
      {/* Background gradients */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-[#E5D5C5]/20 blur-[120px] rounded-full pointer-events-none" />
      
      <div className="max-w-7xl mx-auto px-6 relative z-10 flex flex-col items-center text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-gray-300 mb-8"
        >
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm font-medium">Apex SDR 2.0 is now available</span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="text-5xl md:text-7xl font-extrabold tracking-tight text-white max-w-4xl leading-[1.1]"
        >
          The Autonomous AI Growth Company
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mt-6 text-xl text-gray-400 max-w-2xl leading-relaxed"
        >
          Scale your outbound prospecting with an AI agent that builds lists, crafts hyper-personalized emails, and manages responses — all on autopilot.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mt-10 flex flex-col sm:flex-row items-center gap-4"
        >
          <Link
            href="/demo"
            className="flex items-center gap-2 px-8 py-4 rounded-full bg-[#E5D5C5] text-black font-bold text-lg hover:bg-white transition-colors"
          >
            Book a Live Demo <ArrowRight size={20} />
          </Link>
          <Link
            href="/products/apex-sdr"
            className="flex items-center gap-2 px-8 py-4 rounded-full bg-white/5 text-white border border-white/10 font-bold text-lg hover:bg-white/10 transition-colors"
          >
            View Product Features
          </Link>
        </motion.div>

        {/* Social Proof / Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-8 w-full max-w-4xl"
        >
          <div className="flex flex-col items-center gap-2 p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md">
            <Bot size={32} className="text-[#E5D5C5]" />
            <h3 className="text-3xl font-bold text-white mt-2">10x</h3>
            <p className="text-gray-400 text-sm">More pipeline generated</p>
          </div>
          <div className="flex flex-col items-center gap-2 p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md">
            <Target size={32} className="text-[#E5D5C5]" />
            <h3 className="text-3xl font-bold text-white mt-2">85%</h3>
            <p className="text-gray-400 text-sm">Open rate on AI emails</p>
          </div>
          <div className="flex flex-col items-center gap-2 p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md">
            <Zap size={32} className="text-[#E5D5C5]" />
            <h3 className="text-3xl font-bold text-white mt-2">24/7</h3>
            <p className="text-gray-400 text-sm">Autonomous operation</p>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
