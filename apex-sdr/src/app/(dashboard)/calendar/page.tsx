"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { CalendarCheck2, CalendarClock, Search, XCircle, AlertOctagon } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { fetchApi } from "@/lib/api";
import { EmptyState, ErrorState, CardsSkeleton } from "@/components/ui/DataStates";
import { Pill } from "@/components/ui/Pill";
import { SummaryCard, SearchInput, Th, ThSortable, Pagination } from "@/components/shared/TableBits";
import { formatDateTime, formatRelativeTime } from "@/lib/format";

interface UpcomingMeeting {
  prospect_id: string;
  name: string;
  google_calendar_event_id: string | null;
  booked_at: string | null;
}

interface FailedSync {
  prospect_id: string;
  event_type: string;
  error_message: string | null;
  created_at: string;
}

const PAGE_SIZE = 10;

export default function CalendarPage() {
  const { data, error, isLoading, mutate } = useSWR("/calendar/sync-status", fetchApi);

  const [meetingSearch, setMeetingSearch] = useState("");
  const [meetingSort, setMeetingSort] = useState<"asc" | "desc">("desc");
  const [meetingPage, setMeetingPage] = useState(1);

  const [failedSearch, setFailedSearch] = useState("");
  const [failedSort, setFailedSort] = useState<"asc" | "desc">("desc");
  const [failedPage, setFailedPage] = useState(1);

  const payload = data?.data;
  const upcomingMeetings: UpcomingMeeting[] = useMemo(() => payload?.upcoming_meetings ?? [], [payload]);
  const failedSyncs: FailedSync[] = useMemo(() => payload?.failed_syncs ?? [], [payload]);

  const filteredMeetings = useMemo(() => {
    const q = meetingSearch.trim().toLowerCase();
    const rows = upcomingMeetings.filter((m) => !q || m.name.toLowerCase().includes(q));
    return [...rows].sort((a, b) => {
      const cmp = new Date(a.booked_at ?? 0).getTime() - new Date(b.booked_at ?? 0).getTime();
      return meetingSort === "asc" ? cmp : -cmp;
    });
  }, [upcomingMeetings, meetingSearch, meetingSort]);

  const filteredFailed = useMemo(() => {
    const q = failedSearch.trim().toLowerCase();
    const rows = failedSyncs.filter(
      (f) => !q || f.event_type.toLowerCase().includes(q) || (f.error_message ?? "").toLowerCase().includes(q)
    );
    return [...rows].sort((a, b) => {
      const cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      return failedSort === "asc" ? cmp : -cmp;
    });
  }, [failedSyncs, failedSearch, failedSort]);

  const meetingTotalPages = Math.max(1, Math.ceil(filteredMeetings.length / PAGE_SIZE));
  const meetingClamped = Math.min(meetingPage, meetingTotalPages);
  const meetingRows = filteredMeetings.slice((meetingClamped - 1) * PAGE_SIZE, meetingClamped * PAGE_SIZE);

  const failedTotalPages = Math.max(1, Math.ceil(filteredFailed.length / PAGE_SIZE));
  const failedClamped = Math.min(failedPage, failedTotalPages);
  const failedRows = filteredFailed.slice((failedClamped - 1) * PAGE_SIZE, failedClamped * PAGE_SIZE);

  return (
    <div className="flex h-full flex-col">
      <Header showViewSwitcher={false} showAddProspect={false} />
      <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--apex-bg)" }}>
        <div className="mb-6 flex items-center gap-2">
          <CalendarClock size={20} style={{ color: "var(--apex-accent)" }} />
          <div>
            <h1 className="text-lg font-bold" style={{ color: "var(--apex-text)" }}>
              Calendar
            </h1>
            <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
              Google Calendar sync status, upcoming meetings, and failed syncs.
            </p>
          </div>
        </div>

        {error ? (
          <ErrorState message={error instanceof Error ? error.message : "Failed to load calendar sync status."} onRetry={() => mutate()} />
        ) : isLoading ? (
          <CardsSkeleton count={3} />
        ) : (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <SummaryCard
                label="Last Calendar Sync"
                value={payload?.last_calendar_sync ? formatRelativeTime(payload.last_calendar_sync) : "Never synced"}
                icon={<CalendarCheck2 size={12} />}
              />
              <SummaryCard label="Upcoming Meetings" value={String(payload?.upcoming_meeting_count ?? 0)} icon={<CalendarClock size={12} />} />
              <SummaryCard label="Failed Syncs" value={String(payload?.failed_sync_count ?? 0)} icon={<AlertOctagon size={12} />} />
            </div>

            {/* Upcoming meetings */}
            <section className="mb-8">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold" style={{ color: "var(--apex-text)" }}>
                  Upcoming Meetings
                </h2>
                <SearchInput
                  value={meetingSearch}
                  onChange={(v) => {
                    setMeetingSearch(v);
                    setMeetingPage(1);
                  }}
                  placeholder="Search by prospect name…"
                  icon={<Search size={14} style={{ color: "var(--apex-muted)" }} />}
                />
              </div>

              {upcomingMeetings.length === 0 ? (
                <EmptyState
                  icon={<CalendarClock size={18} />}
                  title="No upcoming meetings"
                  description="Meetings will appear here once a prospect books via the calendar integration."
                />
              ) : filteredMeetings.length === 0 ? (
                <EmptyState title="No meetings match your search" />
              ) : (
                <div className="overflow-hidden rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[560px] text-left text-sm">
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--apex-border)" }}>
                          <Th>Prospect</Th>
                          <Th>Calendar Event</Th>
                          <ThSortable
                            label="Booked"
                            active
                            dir={meetingSort}
                            onClick={() => setMeetingSort((d) => (d === "asc" ? "desc" : "asc"))}
                          />
                        </tr>
                      </thead>
                      <tbody>
                        {meetingRows.map((m) => (
                          <tr key={m.prospect_id} className="table-row-hover" style={{ borderBottom: "1px solid var(--apex-border)" }}>
                            <td className="px-4 py-3 whitespace-nowrap" style={{ color: "var(--apex-text)" }}>
                              {m.name}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: "var(--apex-text-dim)" }}>
                              {m.google_calendar_event_id ?? "—"}
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 text-xs" style={{ color: "var(--apex-text-faint)" }} title={formatDateTime(m.booked_at)}>
                              {formatRelativeTime(m.booked_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <Pagination page={meetingClamped} totalPages={meetingTotalPages} total={filteredMeetings.length} pageSize={PAGE_SIZE} onChange={setMeetingPage} />
                </div>
              )}
            </section>

            {/* Failed syncs */}
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold" style={{ color: "var(--apex-text)" }}>
                  Failed Syncs
                </h2>
                <SearchInput
                  value={failedSearch}
                  onChange={(v) => {
                    setFailedSearch(v);
                    setFailedPage(1);
                  }}
                  placeholder="Search event type or error…"
                  icon={<Search size={14} style={{ color: "var(--apex-muted)" }} />}
                />
              </div>

              {failedSyncs.length === 0 ? (
                <EmptyState icon={<XCircle size={18} />} title="No failed syncs" description="Everything is syncing cleanly with Google Calendar." />
              ) : filteredFailed.length === 0 ? (
                <EmptyState title="No failures match your search" />
              ) : (
                <div className="overflow-hidden rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[640px] text-left text-sm">
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--apex-border)" }}>
                          <Th>Prospect ID</Th>
                          <Th>Event</Th>
                          <Th>Error</Th>
                          <ThSortable label="When" active dir={failedSort} onClick={() => setFailedSort((d) => (d === "asc" ? "desc" : "asc"))} />
                        </tr>
                      </thead>
                      <tbody>
                        {failedRows.map((f, i) => (
                          <tr key={`${f.prospect_id}-${i}`} className="table-row-hover" style={{ borderBottom: "1px solid var(--apex-border)" }}>
                            <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: "var(--apex-text-dim)" }}>
                              {f.prospect_id.slice(0, 8)}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              <Pill tone="danger">{f.event_type}</Pill>
                            </td>
                            <td className="max-w-sm truncate px-4 py-3 text-xs" style={{ color: "var(--apex-text-dim)" }} title={f.error_message ?? ""}>
                              {f.error_message ?? "—"}
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 text-xs" style={{ color: "var(--apex-text-faint)" }} title={formatDateTime(f.created_at)}>
                              {formatRelativeTime(f.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <Pagination page={failedClamped} totalPages={failedTotalPages} total={filteredFailed.length} pageSize={PAGE_SIZE} onChange={setFailedPage} />
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
