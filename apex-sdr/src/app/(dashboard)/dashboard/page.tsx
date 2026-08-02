"use client";

import { motion } from "framer-motion";
import { Header } from "@/components/layout/Header";
import { useGetAnalytics } from "@/hooks/useGetAnalytics";
import {
  Users,
  Mail,
  Phone,
  MessageSquare,
  DollarSign,
  Flame,
} from "lucide-react";

const PRIORITY_COLORS: Record<string, string> = {
  HOT: "#ef4444",
  HIGH: "#f59e0b",
  MEDIUM: "#3b82f6",
  LOW: "#6b7280",
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export default function DashboardPage() {
  const { data, loading, error } = useGetAnalytics();

  const metrics = [
    { label: "Active Prospects", value: data?.totalProspects ?? 0, icon: <Users size={18} />, color: "#3b82f6" },
    { label: "In Email Outreach", value: data?.emailsSent ?? 0, icon: <Mail size={18} />, color: "#22c55e" },
    { label: "In Call Outreach", value: data?.callsMade ?? 0, icon: <Phone size={18} />, color: "#a855f7" },
    { label: "Engaged / Replied", value: data?.replies ?? 0, icon: <MessageSquare size={18} />, color: "#f59e0b" },
  ];

  const qualificationEntries = Object.entries(data?.qualificationDistribution ?? {});
  const qualificationTotal = qualificationEntries.reduce((sum, [, count]) => sum + count, 0);

  return (
    <div className="flex flex-col h-full">
      <Header showViewSwitcher={false} showAddProspect={false} />

      <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--apex-bg)" }}>
        <div className="mb-8">
          <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--apex-text)" }}>
            Good morning! 👋
          </h1>
          <p className="text-sm" style={{ color: "var(--apex-muted)" }}>
            Here&apos;s what&apos;s happening with your outbound today.
          </p>
        </div>

        {error && (
          <div
            className="mb-6 rounded-lg p-3 text-xs"
            style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)", color: "var(--apex-text-dim)" }}
          >
            Couldn&apos;t load live analytics ({error}). Showing zeros until the API is reachable.
          </div>
        )}

        {/* Metric cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {metrics.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className="rounded-xl p-4"
              style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-lg" style={{ background: `${m.color}18`, color: m.color }}>
                  {m.icon}
                </div>
              </div>
              <p className="text-2xl font-bold mb-0.5" style={{ color: "var(--apex-text)" }}>
                {loading ? "—" : m.value.toLocaleString()}
              </p>
              <p className="text-xs" style={{ color: "var(--apex-muted)" }}>{m.label}</p>
            </motion.div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Revenue */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="rounded-xl p-5"
            style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <DollarSign size={16} style={{ color: "var(--apex-gold)" }} />
              <h2 className="text-sm font-semibold" style={{ color: "var(--apex-text)" }}>Revenue Attribution</h2>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-lg font-bold" style={{ color: "var(--apex-text)" }}>
                  {loading ? "—" : formatCurrency(data?.revenue.estimatedPipelineValue ?? 0)}
                </p>
                <p className="text-xs" style={{ color: "var(--apex-muted)" }}>Est. Pipeline Value</p>
              </div>
              <div>
                <p className="text-lg font-bold" style={{ color: "var(--apex-text)" }}>
                  {loading ? "—" : formatCurrency(data?.revenue.meetingValue ?? 0)}
                </p>
                <p className="text-xs" style={{ color: "var(--apex-muted)" }}>Meeting Value</p>
              </div>
              <div>
                <p className="text-lg font-bold" style={{ color: "var(--apex-success)" }}>
                  {loading ? "—" : formatCurrency(data?.revenue.wonValue ?? 0)}
                </p>
                <p className="text-xs" style={{ color: "var(--apex-muted)" }}>Won</p>
              </div>
              <div>
                <p className="text-lg font-bold" style={{ color: "var(--apex-muted)" }}>
                  {loading ? "—" : formatCurrency(data?.revenue.lostValue ?? 0)}
                </p>
                <p className="text-xs" style={{ color: "var(--apex-muted)" }}>Lost</p>
              </div>
            </div>
          </motion.div>

          {/* Qualification distribution */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.36 }}
            className="rounded-xl p-5"
            style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <Flame size={16} style={{ color: "var(--apex-gold)" }} />
              <h2 className="text-sm font-semibold" style={{ color: "var(--apex-text)" }}>Lead Priority Distribution</h2>
            </div>
            {qualificationTotal === 0 ? (
              <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
                {loading ? "Loading…" : "No qualified prospects yet."}
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {qualificationEntries.map(([level, count]) => (
                  <div key={level} className="flex items-center gap-3">
                    <span className="text-xs w-14" style={{ color: "var(--apex-text-dim)" }}>{level}</span>
                    <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "var(--apex-border)" }}>
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${(count / qualificationTotal) * 100}%`,
                          background: PRIORITY_COLORS[level] ?? "#6b7280",
                        }}
                      />
                    </div>
                    <span className="text-xs w-8 text-right" style={{ color: "var(--apex-muted)" }}>{count}</span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
}
