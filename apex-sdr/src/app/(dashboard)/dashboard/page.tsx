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
  Reply,
  CalendarCheck,
  ShieldAlert,
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

  // Live KPI cards: LinkedIn Responses, Meetings Booked, Invalid Data.
  // Same card shell/typography as the block above, added as its own row
  // rather than folded into the existing 4-card grid, so the current
  // layout is left completely undisturbed.
  const kpiCards = [
    {
      label: "LinkedIn Responses",
      value: data?.linkedinResponses ?? 0,
      subtitle: `+${data?.linkedinResponsesToday ?? 0} today`,
      subtitleColor: "var(--apex-success)",
      icon: <Reply size={18} />,
      color: "#0a66c2",
    },
    {
      label: "Meetings Booked",
      value: data?.meetingsBookedTotal ?? 0,
      subtitle: `${data?.meetingsBookedToday ?? 0} scheduled today`,
      subtitleColor: "var(--apex-muted)",
      icon: <CalendarCheck size={18} />,
      color: "#22c55e",
    },
    {
      label: "Invalid Data",
      value: data?.invalidData ?? 0,
      subtitle: "Needs Review",
      subtitleColor: "#ef4444",
      icon: <ShieldAlert size={18} />,
      color: "#ef4444",
      // No dedicated "invalid records" view exists yet to link to - the
      // card is styled as clickable in anticipation of that (per spec:
      // "clicking this card should eventually allow navigation to invalid
      // records"), but doesn't navigate anywhere yet.
      clickable: true,
    },
  ];

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

        {/* Live KPI cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          {kpiCards.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: (metrics.length + i) * 0.08 }}
              className="rounded-xl p-4"
              style={{
                background: "var(--apex-surface)",
                border: "1px solid var(--apex-border)",
                cursor: m.clickable ? "pointer" : undefined,
              }}
              whileHover={m.clickable ? { y: -2, borderColor: m.color } : undefined}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-lg" style={{ background: `${m.color}18`, color: m.color }}>
                  {m.icon}
                </div>
              </div>
              <p className="text-2xl font-bold mb-0.5" style={{ color: "var(--apex-text)" }}>
                {loading ? "—" : m.value.toLocaleString()}
              </p>
              <p className="text-xs mb-1" style={{ color: "var(--apex-muted)" }}>{m.label}</p>
              <p className="text-xs font-medium" style={{ color: m.subtitleColor }}>
                {loading ? " " : m.subtitle}
              </p>
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
