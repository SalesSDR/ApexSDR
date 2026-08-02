"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { ScrollText, Search, Sparkles, Loader2 } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { fetchApi } from "@/lib/api";
import { ProspectPicker } from "@/components/shared/ProspectPicker";
import type { DirectoryProspect } from "@/hooks/useProspectDirectory";
import { EmptyState, ErrorState, RowsSkeleton } from "@/components/ui/DataStates";
import { Pill, type PillTone } from "@/components/ui/Pill";
import { FilterSelect, SearchInput, Th, ThSortable, Pagination } from "@/components/shared/TableBits";
import { formatDateTime, formatRelativeTime, titleCase } from "@/lib/format";

interface DecisionLog {
  id: string;
  decision_type: string;
  reason: string;
  confidence: number | null;
  prospect_status_at_decision: string | null;
  created_at: string;
}

const DECISION_TONE: Record<string, PillTone> = {
  BOOK_MEETING: "success",
  MARK_QUALIFIED: "success",
  MARK_DISQUALIFIED: "danger",
  END_SEQUENCE: "danger",
  WAIT: "neutral",
  RETRY_LATER: "warning",
  SEND_LINKEDIN: "accent",
  SEND_FOLLOWUP: "accent",
  SEND_EMAIL: "cyan",
  SCHEDULE_CALL: "purple",
};

const PAGE_SIZE = 15;

export default function DecisionLogsPage() {
  const [prospect, setProspect] = useState<DirectoryProspect | null>(null);
  const [limit, setLimit] = useState(50);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [preview, setPreview] = useState<{ decision_type: string; reason: string; confidence: number | null } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const { data, error, isLoading, mutate } = useSWR(
    prospect ? `/decisions/${prospect.id}?limit=${limit}` : null,
    fetchApi
  );

  const logs: DecisionLog[] = useMemo(() => data?.data ?? [], [data]);
  const decisionTypes = useMemo(() => Array.from(new Set(logs.map((l) => l.decision_type))).sort(), [logs]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = logs.filter((l) => {
      const matchesSearch = !q || l.reason.toLowerCase().includes(q);
      const matchesType = typeFilter === "ALL" || l.decision_type === typeFilter;
      return matchesSearch && matchesType;
    });
    return [...rows].sort((a, b) => {
      const cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [logs, search, typeFilter, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const clampedPage = Math.min(page, totalPages);
  const pageRows = filtered.slice((clampedPage - 1) * PAGE_SIZE, clampedPage * PAGE_SIZE);

  async function handlePreview() {
    if (!prospect) return;
    setPreviewLoading(true);
    setPreviewError(null);
    setPreview(null);
    try {
      const res = await fetchApi(`/decisions/${prospect.id}/preview`);
      setPreview(res.data);
    } catch (err: unknown) {
      setPreviewError(err instanceof Error ? err.message : "Failed to preview next decision.");
    } finally {
      setPreviewLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <Header showViewSwitcher={false} showAddProspect={false} />
      <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--apex-bg)" }}>
        <div className="mb-6 flex items-center gap-2">
          <ScrollText size={20} style={{ color: "var(--apex-accent)" }} />
          <div>
            <h1 className="text-lg font-bold" style={{ color: "var(--apex-text)" }}>
              Decision Logs
            </h1>
            <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
              The Decision Engine&apos;s audit trail for a specific prospect.
            </p>
          </div>
        </div>

        <div className="mb-6 flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: "var(--apex-text-dim)" }}>
              Prospect
            </label>
            <ProspectPicker value={prospect} onChange={setProspect} />
          </div>
          {prospect && (
            <button
              onClick={handlePreview}
              disabled={previewLoading}
              className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-opacity"
              style={{ background: "var(--apex-accent-glow)", color: "var(--apex-accent)", opacity: previewLoading ? 0.6 : 1 }}
            >
              {previewLoading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
              Preview next decision
            </button>
          )}
        </div>

        {preview && (
          <div className="mb-6 rounded-xl p-4" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
            <div className="mb-1 flex items-center gap-2">
              <Pill tone={DECISION_TONE[preview.decision_type] ?? "neutral"}>{titleCase(preview.decision_type)}</Pill>
              {preview.confidence != null && (
                <span className="text-xs" style={{ color: "var(--apex-muted)" }}>
                  {Math.round(preview.confidence * 100)}% confidence
                </span>
              )}
            </div>
            <p className="text-xs" style={{ color: "var(--apex-text-dim)" }}>
              {preview.reason}
            </p>
          </div>
        )}
        {previewError && (
          <div className="mb-6">
            <ErrorState message={previewError} />
          </div>
        )}

        {!prospect ? (
          <EmptyState
            icon={<ScrollText size={18} />}
            title="Select a prospect to view its decision history"
            description="Decision logs are per-prospect — search for someone above to see every decision the engine has made for them."
          />
        ) : error ? (
          <ErrorState message={error instanceof Error ? error.message : "Failed to load decision logs."} onRetry={() => mutate()} />
        ) : isLoading ? (
          <div className="rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
            <RowsSkeleton rows={6} cols={4} />
          </div>
        ) : logs.length === 0 ? (
          <EmptyState title="No decisions logged yet for this prospect" description="The Decision Engine hasn't evaluated this prospect yet." />
        ) : (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <SearchInput
                value={search}
                onChange={(v) => {
                  setSearch(v);
                  setPage(1);
                }}
                placeholder="Search reason…"
                icon={<Search size={14} style={{ color: "var(--apex-muted)" }} />}
              />
              <FilterSelect
                value={typeFilter}
                onChange={(v) => {
                  setTypeFilter(v);
                  setPage(1);
                }}
                options={[{ value: "ALL", label: "All decision types" }, ...decisionTypes.map((t) => ({ value: t, label: titleCase(t) }))]}
              />
              <FilterSelect
                value={String(limit)}
                onChange={(v) => {
                  setLimit(Number(v));
                  setPage(1);
                }}
                options={[
                  { value: "50", label: "Last 50" },
                  { value: "100", label: "Last 100" },
                  { value: "200", label: "Last 200" },
                ]}
              />
            </div>

            {filtered.length === 0 ? (
              <EmptyState title="No decisions match your filters" />
            ) : (
              <div className="overflow-hidden rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--apex-border)" }}>
                        <Th>Decision</Th>
                        <Th>Confidence</Th>
                        <Th>Status at decision</Th>
                        <Th>Reason</Th>
                        <ThSortable label="When" active dir={sortDir} onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))} />
                      </tr>
                    </thead>
                    <tbody>
                      {pageRows.map((l) => (
                        <tr key={l.id} className="table-row-hover" style={{ borderBottom: "1px solid var(--apex-border)" }}>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <Pill tone={DECISION_TONE[l.decision_type] ?? "neutral"}>{titleCase(l.decision_type)}</Pill>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: "var(--apex-text-dim)" }}>
                            {l.confidence != null ? `${Math.round(l.confidence * 100)}%` : "—"}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: "var(--apex-text-dim)" }}>
                            {l.prospect_status_at_decision ? titleCase(l.prospect_status_at_decision) : "—"}
                          </td>
                          <td className="max-w-md truncate px-4 py-3 text-xs" style={{ color: "var(--apex-text-dim)" }} title={l.reason}>
                            {l.reason}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 text-xs" style={{ color: "var(--apex-text-faint)" }} title={formatDateTime(l.created_at)}>
                            {formatRelativeTime(l.created_at)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination page={clampedPage} totalPages={totalPages} total={filtered.length} pageSize={PAGE_SIZE} onChange={setPage} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
