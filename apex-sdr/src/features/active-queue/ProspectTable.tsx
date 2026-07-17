"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  Mail,
  Phone,
  Users,
} from "lucide-react";

// LinkedIn icon as custom SVG (lucide-react removed it in v1+)
function LinkedInIcon({ size = 13, style }: { size?: number; style?: React.CSSProperties }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" style={style}>
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/>
      <rect x="2" y="9" width="4" height="12"/>
      <circle cx="4" cy="4" r="2"/>
    </svg>
  );
}
import { StageChip } from "@/components/ui/StageChip";
import { ProspectAvatar } from "@/components/ui/ProspectAvatar";
import { CallSummaryPopover } from "@/components/ui/CallSummaryPopover";
import { TableSkeleton } from "@/components/ui/Skeletons";
import type { Prospect } from "@/types";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/store/uiStore";
import { bulkAction, advanceProspect } from "@/lib/api";

type SortKey = "name" | "company" | "linkedin" | "email" | "call" | "lastActivity";
type SortDir = "asc" | "desc" | null;

interface ProspectTableProps {
  prospects: Prospect[];
  loading: boolean;
  error: string | null;
  totalCount?: number;
}

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active || !dir) return <ChevronsUpDown size={12} className="opacity-40" />;
  return dir === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />;
}

const COL_HEADERS: { key: SortKey; label: string; width: string }[] = [
  { key: "name", label: "Prospect", width: "200px" },
  { key: "linkedin", label: "LinkedIn Contact Stage", width: "160px" },
  { key: "email", label: "Email Contact Stage", width: "150px" },
  { key: "call", label: "Call Stage", width: "190px" },
  { key: "lastActivity", label: "Last Activity", width: "110px" },
];

export function ProspectTable({ prospects, loading, error, totalCount }: ProspectTableProps) {
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const { selectedProspects, toggleSelectProspect, selectAllProspects, clearSelectedProspects } = useUIStore();

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : prev === "desc" ? null : "asc"));
      if (sortDir === "desc") setSortKey(null);
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sortedProspects = useCallback(() => {
    if (!sortKey || !sortDir) return prospects;
    return [...prospects].sort((a, b) => {
      let aVal = "";
      let bVal = "";
      if (sortKey === "name") aVal = `${a.firstName} ${a.lastName}`;
      else if (sortKey === "company") aVal = a.company;
      else if (sortKey === "linkedin") aVal = a.linkedInStage;
      else if (sortKey === "email") aVal = a.emailStage;
      else if (sortKey === "call") aVal = a.callStage;
      else if (sortKey === "lastActivity") aVal = a.lastActivityDate;

      if (sortKey === "name") bVal = `${b.firstName} ${b.lastName}`;
      else if (sortKey === "company") bVal = b.company;
      else if (sortKey === "linkedin") bVal = b.linkedInStage;
      else if (sortKey === "email") bVal = b.emailStage;
      else if (sortKey === "call") bVal = b.callStage;
      else if (sortKey === "lastActivity") bVal = b.lastActivityDate;

      return sortDir === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    });
  }, [prospects, sortKey, sortDir])();

  const allSelected = prospects.length > 0 && selectedProspects.length === prospects.length;

  const handleSelectAll = () => {
    if (allSelected) clearSelectedProspects();
    else selectAllProspects(prospects.map((p) => p.id));
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <Users size={32} style={{ color: "var(--apex-muted)" }} />
        <p className="text-sm" style={{ color: "var(--apex-text-dim)" }}>
          Failed to load prospects
        </p>
        <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
          {error}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Table count */}
      <div
        className="flex items-center justify-between px-5 py-2.5 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--apex-border)" }}
      >
        <span className="text-xs" style={{ color: "var(--apex-muted)" }}>
          Active prospects:{" "}
          <span className="font-semibold" style={{ color: "var(--apex-text-dim)" }}>
            {totalCount?.toLocaleString() ?? "1,250"}
          </span>
        </span>
        {selectedProspects.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-2"
          >
            <span className="text-xs font-medium" style={{ color: "var(--apex-accent)" }}>
              {selectedProspects.length} selected
            </span>
            <div className="h-3 w-px bg-white/10 mx-1" />
            <button
              onClick={async () => {
                try {
                  await bulkAction(selectedProspects, "FORCE_ADVANCE");
                  clearSelectedProspects();
                } catch (err) {
                  console.error(err);
                }
              }}
              className="flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold transition-all hover:brightness-110"
              style={{ background: "var(--apex-accent)", color: "white" }}
            >
              Force Advance
            </button>
            <button
              onClick={async () => {
                try {
                  await bulkAction(selectedProspects, "PAUSE");
                  clearSelectedProspects();
                } catch (err) {
                  console.error(err);
                }
              }}
              className="flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-all hover:bg-white/5"
              style={{ border: "1px solid var(--apex-border)", color: "var(--apex-text-dim)" }}
            >
              Pause
            </button>
            <button
              onClick={clearSelectedProspects}
              className="text-xs px-2 py-1 rounded hover:bg-white/5 transition-colors"
              style={{ color: "var(--apex-muted)" }}
            >
              Clear
            </button>
          </motion.div>
        )}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse min-w-max">
          <thead
            className="sticky top-0 z-10"
            style={{ background: "var(--apex-surface-2)" }}
          >
            <tr>
              {/* Checkbox col */}
              <th className="w-10 pl-5 py-3 text-left">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={handleSelectAll}
                  className="rounded w-3.5 h-3.5 cursor-pointer accent-blue-500"
                  aria-label="Select all prospects"
                  id="select-all-checkbox"
                />
              </th>

              {COL_HEADERS.map(({ key, label, width }) => (
                <th
                  key={key}
                  className="py-3 pr-4 text-left cursor-pointer select-none group"
                  style={{ minWidth: width }}
                  onClick={() => handleSort(key)}
                >
                  <div className="flex items-center gap-1">
                    <span
                      className="text-xs font-semibold transition-colors group-hover:text-white"
                      style={{ color: sortKey === key ? "var(--apex-text)" : "var(--apex-muted)" }}
                    >
                      {label}
                    </span>
                    <span
                      style={{
                        color: sortKey === key ? "var(--apex-accent)" : "var(--apex-text-faint)",
                      }}
                    >
                      <SortIcon active={sortKey === key} dir={sortDir} />
                    </span>
                  </div>
                </th>
              ))}

              {/* Actions col */}
              <th className="py-3 pr-5 text-left">
                <span className="text-xs font-semibold" style={{ color: "var(--apex-muted)" }}>
                  Actions
                </span>
              </th>
            </tr>
          </thead>

          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="p-0">
                  <TableSkeleton rows={6} />
                </td>
              </tr>
            ) : sortedProspects.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <div className="flex flex-col items-center justify-center py-20 gap-3">
                    <Users size={36} style={{ color: "var(--apex-border)" }} />
                    <p className="text-sm font-medium" style={{ color: "var(--apex-text-dim)" }}>
                      No prospects yet
                    </p>
                    <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
                      Add prospects or import from your CRM
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              <AnimatePresence initial={false}>
                {sortedProspects.map((prospect, idx) => {
                  const isSelected = selectedProspects.includes(prospect.id);
                  return (
                    <motion.tr
                      key={prospect.id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.04, duration: 0.2 }}
                      className={cn(
                        "table-row-hover transition-colors cursor-pointer border-b",
                        isSelected && "bg-blue-500/5"
                      )}
                      style={{ borderColor: "var(--apex-border)" }}
                      onClick={() => toggleSelectProspect(prospect.id)}
                    >
                      {/* Checkbox */}
                      <td className="pl-5 py-3.5 w-10">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectProspect(prospect.id)}
                          onClick={(e) => e.stopPropagation()}
                          className="rounded w-3.5 h-3.5 cursor-pointer accent-blue-500"
                          aria-label={`Select ${prospect.firstName} ${prospect.lastName}`}
                        />
                      </td>

                      {/* Prospect info */}
                      <td className="py-3.5 pr-4" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center gap-2.5">
                          <ProspectAvatar
                            initials={prospect.avatarInitials}
                            color={prospect.avatarColor}
                          />
                          <div className="min-w-0">
                            <p
                              className="text-xs font-semibold truncate"
                              style={{ color: "var(--apex-text)" }}
                            >
                              {prospect.firstName} {prospect.lastName}
                            </p>
                            <p className="text-xs truncate" style={{ color: "var(--apex-muted)" }}>
                              {prospect.title}
                            </p>
                            <p
                              className="text-xs truncate"
                              style={{ color: "var(--apex-text-faint)" }}
                            >
                              {prospect.company}
                            </p>
                          </div>
                        </div>
                      </td>

                      {/* LinkedIn stage */}
                      <td className="py-3.5 pr-4" onClick={(e) => e.stopPropagation()}>
                        <button 
                          className="hover:scale-105 transition-transform" 
                          onClick={() => advanceProspect(prospect.id)}
                          title="Manually Force Advance"
                        >
                          <StageChip stage={prospect.linkedInStage} variant="linkedin" />
                        </button>
                      </td>

                      {/* Email stage */}
                      <td className="py-3.5 pr-4" onClick={(e) => e.stopPropagation()}>
                        <button 
                          className="hover:scale-105 transition-transform" 
                          onClick={() => advanceProspect(prospect.id)}
                          title="Manually Force Advance"
                        >
                          <StageChip stage={prospect.emailStage} variant="email" />
                        </button>
                      </td>

                      {/* Call stage + optional call summary */}
                      <td className="py-3.5 pr-4" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <button 
                            className="hover:scale-105 transition-transform" 
                            onClick={() => advanceProspect(prospect.id)}
                            title="Manually Force Advance"
                          >
                            <StageChip stage={prospect.callStage} variant="call" />
                          </button>
                          {prospect.callSummary && (
                            <CallSummaryPopover callSummary={prospect.callSummary} />
                          )}
                        </div>
                      </td>

                      {/* Last activity */}
                      <td className="py-3.5 pr-4">
                        <span className="text-xs" style={{ color: "var(--apex-muted)" }}>
                          {prospect.lastActivity}
                        </span>
                      </td>

                      {/* Action icons */}
                      <td className="py-3.5 pr-5" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center gap-1">
                          <a
                            href={prospect.linkedInUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 rounded-md hover:bg-blue-500/10 transition-all group"
                            aria-label={`LinkedIn profile for ${prospect.firstName} ${prospect.lastName}`}
                          >
                            <LinkedInIcon
                              size={13}
                              style={{ color: "#0a66c2" }}
                            />
                          </a>
                          <a
                            href={`mailto:${prospect.email}`}
                            className="p-1.5 rounded-md hover:bg-blue-500/10 transition-all group"
                            aria-label={`Email ${prospect.firstName} ${prospect.lastName}`}
                          >
                            <Mail
                              size={13}
                              className="group-hover:scale-110 transition-transform"
                              style={{ color: "var(--apex-accent)" }}
                            />
                          </a>
                          <a
                            href={`tel:${prospect.phone}`}
                            className="p-1.5 rounded-md hover:bg-green-500/10 transition-all group"
                            aria-label={`Call ${prospect.firstName} ${prospect.lastName}`}
                          >
                            <Phone
                              size={13}
                              className="group-hover:scale-110 transition-transform"
                              style={{ color: "var(--apex-success)" }}
                            />
                          </a>
                        </div>
                      </td>
                    </motion.tr>
                  );
                })}
              </AnimatePresence>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
