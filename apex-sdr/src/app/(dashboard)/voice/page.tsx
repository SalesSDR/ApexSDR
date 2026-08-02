"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { PhoneCall, Search, X, Bot, User as UserIcon, Clock } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { fetchApi } from "@/lib/api";
import { EmptyState, ErrorState, RowsSkeleton, CardsSkeleton } from "@/components/ui/DataStates";
import { Pill, type PillTone } from "@/components/ui/Pill";
import { SummaryCard, FilterSelect, SearchInput, Th, ThSortable, Pagination } from "@/components/shared/TableBits";
import { formatDateTime, formatRelativeTime, formatDuration, titleCase } from "@/lib/format";

interface TranscriptLine {
  turn_index: number;
  speaker: string;
  text: string;
  intent: string | null;
  confidence: number | null;
}

interface Transcript {
  id: string;
  call_sid: string;
  duration_seconds: number;
  total_turns: number;
  status: string;
  summary: string | null;
  incremental_summary: string | null;
  lines: TranscriptLine[];
  created_at: string;
}

const STATUS_TONE: Record<string, PillTone> = {
  COMPLETED: "success",
  IN_PROGRESS: "cyan",
  FAILED: "danger",
};

const PAGE_SIZE = 10;

export default function VoicePage() {
  const { data: statusData, error: statusError, isLoading: statusLoading } = useSWR("/voice/status", fetchApi);
  const { data, error, isLoading, mutate } = useSWR<Transcript[]>("/voice/conversations", fetchApi);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Transcript | null>(null);

  // This endpoint returns the transcript array directly (not wrapped in {status, data}).
  const conversations: Transcript[] = useMemo(() => (Array.isArray(data) ? data : []), [data]);
  const statuses = useMemo(() => Array.from(new Set(conversations.map((c) => c.status))).sort(), [conversations]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = conversations.filter((c) => {
      const matchesSearch = !q || c.call_sid.toLowerCase().includes(q) || (c.summary ?? "").toLowerCase().includes(q);
      const matchesStatus = statusFilter === "ALL" || c.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
    return [...rows].sort((a, b) => {
      const cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [conversations, search, statusFilter, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const clampedPage = Math.min(page, totalPages);
  const pageRows = filtered.slice((clampedPage - 1) * PAGE_SIZE, clampedPage * PAGE_SIZE);

  const completedCount = conversations.filter((c) => c.status === "COMPLETED").length;
  const avgTurns = conversations.length
    ? Math.round(conversations.reduce((sum, c) => sum + c.total_turns, 0) / conversations.length)
    : 0;

  return (
    <div className="flex h-full flex-col">
      <Header showViewSwitcher={false} showAddProspect={false} />
      <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--apex-bg)" }}>
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <PhoneCall size={20} style={{ color: "var(--apex-accent)" }} />
            <div>
              <h1 className="text-lg font-bold" style={{ color: "var(--apex-text)" }}>
                Voice Conversations
              </h1>
              <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
                AI voice call transcripts and outcomes.
              </p>
            </div>
          </div>
          {!statusLoading && !statusError && (
            <Pill tone={statusData?.engine === "active" ? "success" : "neutral"}>Engine {statusData?.engine ?? "unknown"}</Pill>
          )}
        </div>

        {error ? (
          <ErrorState message={error instanceof Error ? error.message : "Failed to load voice conversations."} onRetry={() => mutate()} />
        ) : isLoading ? (
          <>
            <CardsSkeleton count={3} />
            <div className="mt-6 rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
              <RowsSkeleton rows={6} cols={5} />
            </div>
          </>
        ) : conversations.length === 0 ? (
          <EmptyState
            icon={<PhoneCall size={18} />}
            title="No voice conversations yet"
            description="Transcripts will appear here once the AI voice agent completes calls with prospects."
          />
        ) : (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <SummaryCard label="Total Conversations" value={conversations.length.toLocaleString()} icon={<PhoneCall size={12} />} />
              <SummaryCard label="Completed" value={completedCount.toLocaleString()} icon={<Clock size={12} />} />
              <SummaryCard label="Avg. Turns / Call" value={avgTurns.toLocaleString()} />
            </div>

            <div className="mb-4 flex flex-wrap items-center gap-2">
              <SearchInput
                value={search}
                onChange={(v) => {
                  setSearch(v);
                  setPage(1);
                }}
                placeholder="Search call SID or summary…"
                icon={<Search size={14} style={{ color: "var(--apex-muted)" }} />}
              />
              <FilterSelect
                value={statusFilter}
                onChange={(v) => {
                  setStatusFilter(v);
                  setPage(1);
                }}
                options={[{ value: "ALL", label: "All statuses" }, ...statuses.map((s) => ({ value: s, label: titleCase(s) }))]}
              />
            </div>

            {filtered.length === 0 ? (
              <EmptyState title="No conversations match your filters" />
            ) : (
              <div className="overflow-hidden rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--apex-border)" }}>
                        <Th>Call SID</Th>
                        <Th>Status</Th>
                        <Th>Duration</Th>
                        <Th>Turns</Th>
                        <Th>Summary</Th>
                        <ThSortable label="When" active dir={sortDir} onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))} />
                      </tr>
                    </thead>
                    <tbody>
                      {pageRows.map((c) => (
                        <tr
                          key={c.id}
                          onClick={() => setSelected(c)}
                          className="table-row-hover cursor-pointer"
                          style={{ borderBottom: "1px solid var(--apex-border)" }}
                        >
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-xs" style={{ color: "var(--apex-text)" }}>
                            {c.call_sid}
                          </td>
                          <td className="px-4 py-3">
                            <Pill tone={STATUS_TONE[c.status] ?? "neutral"}>{titleCase(c.status)}</Pill>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: "var(--apex-text-dim)" }}>
                            {formatDuration(c.duration_seconds)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: "var(--apex-text-dim)" }}>
                            {c.total_turns}
                          </td>
                          <td className="max-w-xs truncate px-4 py-3 text-xs" style={{ color: "var(--apex-text-dim)" }} title={c.summary ?? ""}>
                            {c.summary ?? "—"}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 text-xs" style={{ color: "var(--apex-text-faint)" }} title={formatDateTime(c.created_at)}>
                            {formatRelativeTime(c.created_at)}
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

      {selected && <TranscriptDrawer transcript={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function TranscriptDrawer({ transcript, onClose }: { transcript: Transcript; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/50" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="flex h-full w-full max-w-lg flex-col shadow-2xl"
        style={{ background: "var(--apex-surface)", borderLeft: "1px solid var(--apex-border)" }}
      >
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid var(--apex-border)" }}>
          <div>
            <h2 className="font-mono text-sm font-semibold" style={{ color: "var(--apex-text)" }}>
              {transcript.call_sid}
            </h2>
            <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
              {formatDateTime(transcript.created_at)} · {formatDuration(transcript.duration_seconds)} · {transcript.total_turns} turns
            </p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 hover:bg-white/5" style={{ color: "var(--apex-muted)" }} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {transcript.summary && (
          <div className="px-5 py-3 text-xs" style={{ borderBottom: "1px solid var(--apex-border)", color: "var(--apex-text-dim)" }}>
            <span className="font-medium" style={{ color: "var(--apex-text)" }}>
              Summary:{" "}
            </span>
            {transcript.summary}
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-5">
          {transcript.lines.length === 0 ? (
            <EmptyState title="No transcript lines recorded for this call." />
          ) : (
            <div className="flex flex-col gap-3">
              {transcript.lines.map((line) => {
                const isAssistant = line.speaker === "ASSISTANT";
                return (
                  <div key={line.turn_index} className={`flex gap-2.5 ${isAssistant ? "" : "flex-row-reverse"}`}>
                    <div
                      className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full"
                      style={{ background: isAssistant ? "var(--apex-accent-glow)" : "var(--apex-surface-3)", color: isAssistant ? "var(--apex-accent)" : "var(--apex-text-dim)" }}
                    >
                      {isAssistant ? <Bot size={13} /> : <UserIcon size={13} />}
                    </div>
                    <div
                      className="max-w-[80%] rounded-xl px-3 py-2 text-xs"
                      style={{
                        background: isAssistant ? "var(--apex-surface-2)" : "var(--apex-accent-glow)",
                        color: "var(--apex-text)",
                      }}
                    >
                      <p>{line.text}</p>
                      {line.intent && (
                        <p className="mt-1 text-[10px]" style={{ color: "var(--apex-text-faint)" }}>
                          Intent: {line.intent}
                          {line.confidence != null ? ` (${Math.round(line.confidence * 100)}%)` : ""}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
