"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Sparkles,
  ChevronRight,
  Upload,
  Download,
  UserPlus,
  LayoutGrid,
  List,
  Table2,
  ChevronDown,
  CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/store/uiStore";
import { useState } from "react";
import { AddProspectModal } from "@/components/prospects/AddProspectModal";

const BREADCRUMB_MAP: Record<string, { label: string; parent?: string; parentHref?: string }> = {
  "/dashboard": { label: "Dashboard" },
  "/ai-copilot": { label: "AI Co-pilot" },
  "/prospect": { label: "Prospect" },
  "/prospect/active-queue": { label: "Active Prospects Queue", parent: "Prospect", parentHref: "/prospect" },
  "/prospect/engage-queue": { label: "Engage Queue", parent: "Prospect", parentHref: "/prospect" },
  "/prospect/define-icp": { label: "Define Apex SDR ICP", parent: "Prospect", parentHref: "/prospect" },
  "/prospect/search": { label: "Search", parent: "Prospect", parentHref: "/prospect" },
  "/prospect/sequences": { label: "Sequences", parent: "Prospect", parentHref: "/prospect" },
  "/prospect/crm-sync": { label: "CRM Sync", parent: "Prospect", parentHref: "/prospect" },
  "/engage": { label: "Engage" },
  "/admin-settings": { label: "Admin Settings" },
};

interface HeaderProps {
  showAddProspect?: boolean;
  showUploadDownload?: boolean;
  showResearchButton?: boolean;
  showViewSwitcher?: boolean;
  totalCount?: string;
  totalCountLabel?: string;
}

export function Header({
  showAddProspect = true,
  showUploadDownload = false,
  showResearchButton = false,
  showViewSwitcher = true,
  totalCount,
  totalCountLabel,
}: HeaderProps) {
  const pathname = usePathname();
  const { viewMode, setViewMode } = useUIStore();
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const breadcrumb = BREADCRUMB_MAP[pathname];

  return (
    <header
      className="flex-shrink-0 flex flex-col"
      style={{
        background: "var(--apex-surface)",
        borderBottom: "1px solid var(--apex-border)",
      }}
    >
      {/* ── Top bar ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 h-14 gap-4">
        {/* Breadcrumb */}
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 min-w-0">
          {breadcrumb?.parent && (
            <>
              <Link
                href={breadcrumb.parentHref!}
                className="text-sm font-medium hover:text-white transition-colors whitespace-nowrap"
                style={{ color: "var(--apex-muted)" }}
              >
                {breadcrumb.parent}
              </Link>
              <ChevronRight size={14} style={{ color: "var(--apex-text-faint)" }} className="flex-shrink-0" />
            </>
          )}
          <h1 className="text-sm font-semibold whitespace-nowrap overflow-hidden text-ellipsis" style={{ color: "var(--apex-text)" }}>
            {breadcrumb?.label ?? "Apex SDR"}
          </h1>
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {showResearchButton && (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              style={{
                background: "rgba(59,130,246,0.12)",
                border: "1px solid rgba(59,130,246,0.25)",
                color: "var(--apex-accent)",
              }}
              id="research-apex-ai-btn"
            >
              <Sparkles size={13} className="sparkle-animate" />
              Research with Apex AI
            </motion.button>
          )}

          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{
              background: "rgba(245,158,11,0.1)",
              border: "1px solid rgba(245,158,11,0.25)",
              color: "var(--apex-gold)",
            }}
            id="use-apollo-ai-btn"
          >
            <Sparkles size={13} />
            Use Apollo AI
          </motion.button>

          {showAddProspect && (
            <>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setIsAddModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                style={{
                  background: "var(--apex-accent)",
                  color: "white",
                }}
                id="add-prospect-btn"
              >
                <UserPlus size={13} />
                Add Prospect
              </motion.button>

              <AddProspectModal
                isOpen={isAddModalOpen}
                onClose={() => setIsAddModalOpen(false)}
                onSuccess={() => {
                  console.log("Prospect added successfully");
                  // Optionally trigger a global refetch, but SSE handles it!
                }}
              />
            </>
          )}

          {showUploadDownload && (
            <>
              <button
                className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                style={{ color: "var(--apex-muted)" }}
                aria-label="Upload"
                id="upload-btn"
              >
                <Upload size={15} />
              </button>
              <button
                className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                style={{ color: "var(--apex-muted)" }}
                aria-label="Download"
                id="download-btn"
              >
                <Download size={15} />
              </button>
            </>
          )}

          {/* Onboarding dropdown */}
          <div className="relative">
            <button
              onClick={() => setOnboardingOpen(!onboardingOpen)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all hover:bg-white/5"
              style={{
                border: "1px solid var(--apex-border)",
                color: "var(--apex-text-dim)",
              }}
              id="onboarding-status-btn"
              aria-expanded={onboardingOpen}
            >
              <div
                className="w-4 h-4 rounded-full flex-shrink-0"
                style={{
                  background: `conic-gradient(#3b82f6 144deg, rgba(255,255,255,0.15) 144deg)`,
                }}
              />
              <span className="hidden sm:inline whitespace-nowrap">Apex Onboarding</span>
              <ChevronDown size={12} className={cn("transition-transform", onboardingOpen && "rotate-180")} />
            </button>

            {onboardingOpen && (
              <motion.div
                initial={{ opacity: 0, y: -8, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -8 }}
                className="absolute right-0 top-full mt-2 w-64 rounded-xl p-4 z-50"
                style={{
                  background: "var(--apex-surface-2)",
                  border: "1px solid var(--apex-border)",
                  boxShadow: "0 20px 40px rgba(0,0,0,0.4)",
                }}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-semibold" style={{ color: "var(--apex-text)" }}>
                    Apex Onboarding
                  </span>
                  <span className="text-xs font-medium" style={{ color: "var(--apex-accent)" }}>
                    40%
                  </span>
                </div>
                <div
                  className="h-1.5 rounded-full overflow-hidden mb-4"
                  style={{ background: "rgba(255,255,255,0.08)" }}
                >
                  <div
                    className="h-full rounded-full"
                    style={{ width: "40%", background: "linear-gradient(90deg, #3b82f6, #60a5fa)" }}
                  />
                </div>
                <div className="space-y-2">
                  {[
                    { label: "Connect CRM", done: true },
                    { label: "Define ICP", done: true },
                    { label: "Import Prospects", done: false },
                    { label: "Set Up Sequences", done: false },
                    { label: "Launch Campaign", done: false },
                  ].map((step, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <CheckCircle2
                        size={14}
                        style={{ color: step.done ? "var(--apex-success)" : "var(--apex-text-faint)" }}
                      />
                      <span
                        className="text-xs"
                        style={{ color: step.done ? "var(--apex-text-dim)" : "var(--apex-text-faint)" }}
                      >
                        {step.label}
                      </span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </div>
        </div>
      </div>

      {/* ── Sub-toolbar (View Switcher) ──────────────────────────── */}
      {showViewSwitcher && (
        <div
          className="flex items-center gap-3 px-5 py-2"
          style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}
        >
          <span className="text-xs" style={{ color: "var(--apex-muted)" }}>
            View
          </span>
          <div
            className="flex items-center gap-0.5 p-0.5 rounded-lg"
            style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)" }}
          >
            {[
              { mode: "list" as const, icon: <List size={13} />, label: "List view" },
              { mode: "grid" as const, icon: <Table2 size={13} />, label: "Grid view" },
              { mode: "card" as const, icon: <LayoutGrid size={13} />, label: "Card view" },
            ].map(({ mode, icon, label }) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                aria-label={label}
                className="p-1.5 rounded-md transition-all"
                style={{
                  background: viewMode === mode ? "var(--apex-surface-3)" : "transparent",
                  color: viewMode === mode ? "var(--apex-text)" : "var(--apex-muted)",
                  border: viewMode === mode ? "1px solid var(--apex-border)" : "1px solid transparent",
                }}
                id={`view-${mode}-btn`}
              >
                {icon}
              </button>
            ))}
          </div>

          {totalCount && (
            <span className="text-xs ml-auto" style={{ color: "var(--apex-muted)" }}>
              {totalCountLabel ?? "Total"}:{" "}
              <span style={{ color: "var(--apex-text-dim)" }} className="font-medium">
                {totalCount}
              </span>
            </span>
          )}
        </div>
      )}
    </header>
  );
}
