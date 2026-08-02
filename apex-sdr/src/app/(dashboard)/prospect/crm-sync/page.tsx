"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { RefreshCw, CheckCircle2, XCircle } from "lucide-react";
import { fetchApi } from "@/lib/api";

interface CrmSyncMetrics {
  total_prospects: number;
  contacts_synced: number;
  deals_created: number;
  sync_coverage_pct: number;
  deals_by_stage: Record<string, number>;
}

export default function CRMSyncPage() {
  const [metrics, setMetrics] = useState<CrmSyncMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchApi("/analytics/metrics/crm-sync")
      .then((res) => {
        if (!cancelled) setMetrics(res.data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load CRM sync status");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col h-full">
      <Header showViewSwitcher={false} showAddProspect={false} />
      <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--apex-bg)" }}>
        <div className="flex items-center gap-2 mb-6">
          <RefreshCw size={20} style={{ color: "var(--apex-accent)" }} />
          <h1 className="text-lg font-bold" style={{ color: "var(--apex-text)" }}>HubSpot CRM Sync</h1>
        </div>

        {loading && <p className="text-sm" style={{ color: "var(--apex-muted)" }}>Loading sync status…</p>}
        {error && (
          <p className="text-sm" style={{ color: "var(--apex-danger, #ef4444)" }}>
            Couldn&apos;t load CRM sync status: {error}
          </p>
        )}

        {metrics && (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="rounded-xl p-4" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                <p className="text-2xl font-bold" style={{ color: "var(--apex-text)" }}>{metrics.total_prospects.toLocaleString()}</p>
                <p className="text-xs" style={{ color: "var(--apex-muted)" }}>Total Prospects</p>
              </div>
              <div className="rounded-xl p-4" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 size={14} style={{ color: "var(--apex-success)" }} />
                  <p className="text-2xl font-bold" style={{ color: "var(--apex-text)" }}>{metrics.contacts_synced.toLocaleString()}</p>
                </div>
                <p className="text-xs" style={{ color: "var(--apex-muted)" }}>Contacts Synced</p>
              </div>
              <div className="rounded-xl p-4" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                <p className="text-2xl font-bold" style={{ color: "var(--apex-text)" }}>{metrics.deals_created.toLocaleString()}</p>
                <p className="text-xs" style={{ color: "var(--apex-muted)" }}>Deals Created</p>
              </div>
              <div className="rounded-xl p-4" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                <p className="text-2xl font-bold" style={{ color: "var(--apex-text)" }}>{metrics.sync_coverage_pct}%</p>
                <p className="text-xs" style={{ color: "var(--apex-muted)" }}>Sync Coverage</p>
              </div>
            </div>

            <div className="rounded-xl p-5" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
              <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--apex-text)" }}>Deals by Stage</h2>
              {Object.keys(metrics.deals_by_stage).length === 0 ? (
                <p className="text-xs" style={{ color: "var(--apex-muted)" }}>No deals synced yet.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {Object.entries(metrics.deals_by_stage).map(([stage, count]) => (
                    <div key={stage} className="flex items-center justify-between text-xs">
                      <span style={{ color: "var(--apex-text-dim)" }}>{stage}</span>
                      <span style={{ color: "var(--apex-muted)" }}>{count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {!loading && !error && !metrics?.total_prospects && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <XCircle size={32} className="mb-3" style={{ color: "var(--apex-border)" }} />
            <p className="text-sm" style={{ color: "var(--apex-text-dim)" }}>No prospects synced to HubSpot yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}
