"use client";

import { motion } from "framer-motion";
import { Header } from "@/components/layout/Header";
import {
  TrendingUp,
  Users,
  Mail,
  Phone,
  ArrowUpRight,
  Sparkles,
  Activity,
} from "lucide-react";

const METRICS = [
  { label: "Active Prospects", value: "1,250", change: "+12%", icon: <Users size={18} />, color: "#3b82f6" },
  { label: "Emails Sent", value: "3,847", change: "+8%", icon: <Mail size={18} />, color: "#22c55e" },
  { label: "Calls Made", value: "642", change: "+23%", icon: <Phone size={18} />, color: "#a855f7" },
  { label: "Replies", value: "189", change: "+31%", icon: <Activity size={18} />, color: "#f59e0b" },
];

export default function DashboardPage() {
  return (
    <div className="flex flex-col h-full">
      <Header showViewSwitcher={false} showAddProspect={false} />

      <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--apex-bg)" }}>
        {/* Welcome */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--apex-text)" }}>
            Good morning! 👋
          </h1>
          <p className="text-sm" style={{ color: "var(--apex-muted)" }}>
            Here&apos;s what&apos;s happening with your outbound today.
          </p>
        </div>

        {/* Metric cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {METRICS.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className="rounded-xl p-4"
              style={{
                background: "var(--apex-surface)",
                border: "1px solid var(--apex-border)",
              }}
            >
              <div className="flex items-center justify-between mb-3">
                <div
                  className="p-2 rounded-lg"
                  style={{ background: `${m.color}18`, color: m.color }}
                >
                  {m.icon}
                </div>
                <span
                  className="flex items-center gap-0.5 text-xs font-medium"
                  style={{ color: "var(--apex-success)" }}
                >
                  <ArrowUpRight size={12} />
                  {m.change}
                </span>
              </div>
              <p className="text-2xl font-bold mb-0.5" style={{ color: "var(--apex-text)" }}>
                {m.value}
              </p>
              <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
                {m.label}
              </p>
            </motion.div>
          ))}
        </div>

        {/* Coming Soon Banner */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="rounded-2xl p-8 flex flex-col items-center justify-center text-center"
          style={{
            background: "linear-gradient(135deg, rgba(59,130,246,0.08), rgba(168,85,247,0.08))",
            border: "1px solid var(--apex-border)",
          }}
        >
          <Sparkles size={32} className="mb-4 sparkle-animate" style={{ color: "var(--apex-gold)" }} />
          <h2 className="text-lg font-bold mb-2" style={{ color: "var(--apex-text)" }}>
            Analytics Dashboard
          </h2>
          <p className="text-sm max-w-md" style={{ color: "var(--apex-muted)" }}>
            Full analytics with conversion funnels, sequence performance, and AI-powered insights are coming soon.
          </p>
        </motion.div>
      </div>
    </div>
  );
}
