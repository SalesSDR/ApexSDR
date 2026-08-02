"use client";

import { Header } from "@/components/layout/Header";
import { ProspectTable } from "@/features/active-queue/ProspectTable";
import { useGetProspects } from "@/hooks/useGetProspects";
import { useProspectStream } from "@/hooks/useProspectStream";

export default function EngageQueuePage() {
  const { data: prospects, loading, error, refetch } = useGetProspects();

  useProspectStream((event) => {
    console.log("Received SSE event, refetching prospects:", event);
    refetch();
  });

  return (
    <div className="flex flex-col h-full min-h-0">
      <Header
        showViewSwitcher
        showAddProspect
        showUploadDownload
      />
      <div
        className="flex-shrink-0 px-5 py-3"
        style={{ background: "var(--apex-surface)", borderBottom: "1px solid var(--apex-border)" }}
      >
        <h2 className="text-sm font-semibold" style={{ color: "var(--apex-text)" }}>
          Engage Queue:{" "}
          <span style={{ color: "var(--apex-gold)" }}>Active Sequences</span>
        </h2>
      </div>
      <div className="flex-1 min-h-0 overflow-hidden" style={{ background: "var(--apex-surface)" }}>
        <ProspectTable prospects={prospects} loading={loading} error={error} totalCount={prospects.length} />
      </div>
    </div>
  );
}
