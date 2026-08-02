"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { ShieldCheck, ShieldAlert, Search, Ban, Check, Loader2 } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { fetchApi } from "@/lib/api";
import { useProspectDirectory } from "@/hooks/useProspectDirectory";
import { EmptyState, ErrorState, RowsSkeleton, CardsSkeleton } from "@/components/ui/DataStates";
import { Pill, type PillTone } from "@/components/ui/Pill";
import { SummaryCard, FilterSelect, SearchInput, Th, ThSortable, Pagination } from "@/components/shared/TableBits";
import { formatDateTime, formatRelativeTime, titleCase } from "@/lib/format";

interface ComplianceLog {
  id: string;
  prospect_id: string | null;
  policy_type: string;
  severity: "INFO" | "WARNING" | "TEMPORARY_BLOCK" | "PERMANENT_BLOCK";
  channel: string | null;
  reason: string;
  created_at: string;
}

const SEVERITY_TONE: Record<string, PillTone> = {
  INFO: "cyan",
  WARNING: "warning",
  TEMPORARY_BLOCK: "gold",
  PERMANENT_BLOCK: "danger",
};

const PAGE_SIZE = 12;

export default function CompliancePage() {
  const { data: statusData, error: statusError, isLoading: statusLoading } = useSWR("/compliance/status", fetchApi);
  const { data: violationsData, error: violationsError, isLoading: violationsLoading, mutate: mutateViolations } = useSWR(
    "/compliance/violations",
    fetchApi
  );
  const { byId } = useProspectDirectory();

  const [search, setSearch] = useState("");
  const [policyFilter, setPolicyFilter] = useState("ALL");
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);

  const violations: ComplianceLog[] = useMemo(() => violationsData?.data ?? [], [violationsData]);
  const policyTypes = useMemo(() => Array.from(new Set(violations.map((v) => v.policy_type))).sort(), [violations]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = violations.filter((v) => {
      const prospectName = v.prospect_id ? byId.get(v.prospect_id)?.name ?? "" : "";
      const matchesSearch = !q || v.reason.toLowerCase().includes(q) || prospectName.toLowerCase().includes(q);
      const matchesPolicy = policyFilter === "ALL" || v.policy_type === policyFilter;
      const matchesSeverity = severityFilter === "ALL" || v.severity === severityFilter;
      return matchesSearch && matchesPolicy && matchesSeverity;
    });
    return [...rows].sort((a, b) => {
      const cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [violations, search, policyFilter, severityFilter, sortDir, byId]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const clampedPage = Math.min(page, totalPages);
  const pageRows = filtered.slice((clampedPage - 1) * PAGE_SIZE, clampedPage * PAGE_SIZE);
  const permanentBlocks = violations.filter((v) => v.severity === "PERMANENT_BLOCK").length;

  return (
    <div className="flex h-full flex-col">
      <Header showViewSwitcher={false} showAddProspect={false} />
      <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--apex-bg)" }}>
        <div className="mb-6 flex items-center gap-2">
          <ShieldCheck size={20} style={{ color: "var(--apex-accent)" }} />
          <div>
            <h1 className="text-lg font-bold" style={{ color: "var(--apex-text)" }}>
              Compliance
            </h1>
            <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
              Enforced outreach policies and the audit trail of blocked actions.
            </p>
          </div>
        </div>

        {/* Engine status */}
        {statusError ? (
          <div className="mb-6">
            <ErrorState message={statusError instanceof Error ? statusError.message : "Failed to load compliance engine status."} />
          </div>
        ) : statusLoading ? (
          <div className="mb-6">
            <CardsSkeleton count={1} />
          </div>
        ) : (
          <div
            className="mb-6 flex flex-wrap items-center gap-3 rounded-xl p-4"
            style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}
          >
            <Pill tone="success" icon={<Check size={11} />}>
              Engine {statusData?.data?.engine ?? "unknown"}
            </Pill>
            <span className="text-xs" style={{ color: "var(--apex-muted)" }}>
              Enforced policies:
            </span>
            {(statusData?.data?.enforced_policies ?? []).map((p: string) => (
              <Pill key={p} tone="accent">
                {titleCase(p)}
              </Pill>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          {/* Violations */}
          <section>
            <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <SummaryCard label="Logged Violations" value={violations.length.toLocaleString()} icon={<ShieldAlert size={12} />} />
              <SummaryCard label="Permanent Blocks" value={permanentBlocks.toLocaleString()} icon={<Ban size={12} />} />
            </div>

            {violationsError ? (
              <ErrorState
                message={violationsError instanceof Error ? violationsError.message : "Failed to load compliance violations."}
                onRetry={() => mutateViolations()}
              />
            ) : violationsLoading ? (
              <div className="rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                <RowsSkeleton rows={6} cols={4} />
              </div>
            ) : violations.length === 0 ? (
              <EmptyState
                icon={<ShieldCheck size={18} />}
                title="No compliance violations logged"
                description="Every outreach action so far has passed compliance checks (business hours, do-not-contact) cleanly."
              />
            ) : (
              <>
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <SearchInput
                    value={search}
                    onChange={(v) => {
                      setSearch(v);
                      setPage(1);
                    }}
                    placeholder="Search reason or prospect…"
                    icon={<Search size={14} style={{ color: "var(--apex-muted)" }} />}
                  />
                  <FilterSelect
                    value={policyFilter}
                    onChange={(v) => {
                      setPolicyFilter(v);
                      setPage(1);
                    }}
                    options={[{ value: "ALL", label: "All policies" }, ...policyTypes.map((p) => ({ value: p, label: titleCase(p) }))]}
                  />
                  <FilterSelect
                    value={severityFilter}
                    onChange={(v) => {
                      setSeverityFilter(v);
                      setPage(1);
                    }}
                    options={[
                      { value: "ALL", label: "All severities" },
                      { value: "PERMANENT_BLOCK", label: "Permanent Block" },
                      { value: "TEMPORARY_BLOCK", label: "Temporary Block" },
                      { value: "WARNING", label: "Warning" },
                      { value: "INFO", label: "Info" },
                    ]}
                  />
                </div>

                {filtered.length === 0 ? (
                  <EmptyState title="No violations match your filters" />
                ) : (
                  <div className="overflow-hidden rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[640px] text-left text-sm">
                        <thead>
                          <tr style={{ borderBottom: "1px solid var(--apex-border)" }}>
                            <Th>Prospect</Th>
                            <Th>Policy</Th>
                            <Th>Severity</Th>
                            <Th>Reason</Th>
                            <ThSortable label="When" active dir={sortDir} onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))} />
                          </tr>
                        </thead>
                        <tbody>
                          {pageRows.map((v) => (
                            <tr key={v.id} className="table-row-hover" style={{ borderBottom: "1px solid var(--apex-border)" }}>
                              <td className="px-4 py-3 whitespace-nowrap" style={{ color: "var(--apex-text)" }}>
                                {v.prospect_id ? byId.get(v.prospect_id)?.name ?? v.prospect_id.slice(0, 8) : "—"}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: "var(--apex-text-dim)" }}>
                                {titleCase(v.policy_type)}
                              </td>
                              <td className="px-4 py-3">
                                <Pill tone={SEVERITY_TONE[v.severity] ?? "neutral"}>{titleCase(v.severity)}</Pill>
                              </td>
                              <td className="max-w-xs truncate px-4 py-3 text-xs" style={{ color: "var(--apex-text-dim)" }} title={v.reason}>
                                {v.reason}
                              </td>
                              <td className="whitespace-nowrap px-4 py-3 text-xs" style={{ color: "var(--apex-text-faint)" }} title={formatDateTime(v.created_at)}>
                                {formatRelativeTime(v.created_at)}
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
          </section>

          {/* Add to DNC */}
          <AddToDncPanel />
        </div>
      </div>
    </div>
  );
}

function AddToDncPanel() {
  const [value, setValue] = useState("");
  const [type, setType] = useState("EMAIL");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<"success" | "error" | null>(null);
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;
    setSubmitting(true);
    setResult(null);
    try {
      await fetchApi("/compliance/dnc", {
        method: "POST",
        body: JSON.stringify({ value: value.trim(), type, reason: reason.trim() || undefined, source: "USER_MANUAL" }),
      });
      setResult("success");
      setValue("");
      setReason("");
    } catch (err: unknown) {
      setResult("error");
      setErrorMessage(err instanceof Error ? err.message : "Failed to add entry.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <aside className="h-fit rounded-xl p-5" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
      <div className="mb-1 flex items-center gap-2">
        <Ban size={15} style={{ color: "var(--apex-danger)" }} />
        <h2 className="text-sm font-semibold" style={{ color: "var(--apex-text)" }}>
          Add to Do-Not-Contact
        </h2>
      </div>
      <p className="mb-4 text-xs" style={{ color: "var(--apex-text-dim)" }}>
        Manually block an email, domain, or phone number from all future outreach.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium" style={{ color: "var(--apex-text-dim)" }}>
            Type
          </label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="w-full rounded-lg px-3 py-2 text-sm outline-none"
            style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)", color: "var(--apex-text)" }}
          >
            <option value="EMAIL">Email</option>
            <option value="DOMAIN">Domain</option>
            <option value="PHONE">Phone</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium" style={{ color: "var(--apex-text-dim)" }}>
            Value
          </label>
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={type === "EMAIL" ? "someone@example.com" : type === "DOMAIN" ? "example.com" : "+15551234567"}
            className="w-full rounded-lg px-3 py-2 text-sm outline-none"
            style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)", color: "var(--apex-text)" }}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium" style={{ color: "var(--apex-text-dim)" }}>
            Reason (optional)
          </label>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Requested removal"
            className="w-full rounded-lg px-3 py-2 text-sm outline-none"
            style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)", color: "var(--apex-text)" }}
          />
        </div>
        <button
          type="submit"
          disabled={submitting || !value.trim()}
          className="mt-1 flex items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition-opacity"
          style={{ background: "var(--apex-danger)", color: "white", opacity: submitting || !value.trim() ? 0.6 : 1 }}
        >
          {submitting ? <Loader2 size={14} className="animate-spin" /> : <Ban size={14} />}
          {submitting ? "Adding…" : "Add to DNC"}
        </button>

        {result === "success" && (
          <p className="text-xs" style={{ color: "var(--apex-success)" }}>
            Added successfully.
          </p>
        )}
        {result === "error" && (
          <p className="text-xs" style={{ color: "var(--apex-danger)" }}>
            {errorMessage}
          </p>
        )}
      </form>
    </aside>
  );
}
