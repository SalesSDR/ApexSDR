"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ChevronRight,
  Upload,
  Download,
  UserPlus,
  LayoutGrid,
  List,
  Table2,
} from "lucide-react";
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
  "/calendar": { label: "Calendar" },
  "/voice": { label: "Voice" },
  "/buying-signals": { label: "Buying Signals" },
  "/decision-logs": { label: "Decision Logs" },
  "/conversation-memory": { label: "Conversation Memory" },
  "/compliance": { label: "Compliance" },
  "/admin-settings": { label: "Admin Settings" },
};

interface HeaderProps {
  showAddProspect?: boolean;
  showUploadDownload?: boolean;
  showViewSwitcher?: boolean;
  totalCount?: string;
  totalCountLabel?: string;
}

export function Header({
  showAddProspect = true,
  showUploadDownload = false,
  showViewSwitcher = true,
  totalCount,
  totalCountLabel,
}: HeaderProps) {
  const pathname = usePathname();
  const { viewMode, setViewMode } = useUIStore();
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
