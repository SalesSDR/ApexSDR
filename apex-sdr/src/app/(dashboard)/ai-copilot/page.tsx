"use client";

import { motion } from "framer-motion";
import { Header } from "@/components/layout/Header";
import { Bot, Sparkles, MessageSquare, Zap } from "lucide-react";

export default function AICopilotPage() {
  return (
    <div className="flex flex-col h-full">
      <Header showViewSwitcher={false} showAddProspect={false} />
      <div
        className="flex-1 flex flex-col items-center justify-center gap-6 p-8"
        style={{ background: "var(--apex-bg)" }}
      >
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 200 }}
          className="w-20 h-20 rounded-2xl flex items-center justify-center"
          style={{
            background: "linear-gradient(135deg, rgba(59,130,246,0.2), rgba(168,85,247,0.2))",
            border: "1px solid rgba(59,130,246,0.3)",
          }}
        >
          <Bot size={36} style={{ color: "var(--apex-accent)" }} />
        </motion.div>
        <div className="text-center max-w-md">
          <h1 className="text-xl font-bold mb-2" style={{ color: "var(--apex-text)" }}>
            AI Co-pilot
          </h1>
          <p className="text-sm mb-6" style={{ color: "var(--apex-muted)" }}>
            Your intelligent sales assistant that analyzes prospects, crafts personalized outreach, and surfaces the best opportunities.
          </p>
          <div className="flex flex-col gap-2">
            {[
              { icon: <MessageSquare size={14} />, text: "Personalized message generation" },
              { icon: <Sparkles size={14} />, text: "AI-powered prospect scoring" },
              { icon: <Zap size={14} />, text: "Smart sequence recommendations" },
            ].map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 + i * 0.08 }}
                className="flex items-center gap-2.5 px-4 py-2.5 rounded-lg"
                style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}
              >
                <span style={{ color: "var(--apex-accent)" }}>{item.icon}</span>
                <span className="text-xs" style={{ color: "var(--apex-text-dim)" }}>{item.text}</span>
                <span
                  className="ml-auto text-xs px-1.5 py-0.5 rounded"
                  style={{ background: "rgba(34,197,94,0.12)", color: "var(--apex-success)" }}
                >
                  Live
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
