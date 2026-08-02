/* eslint-disable react-hooks/set-state-in-effect -- matches the established
   data-fetching hook pattern in useGetProspects.ts: fetchData is also the
   public refetch() callback, so it can't be restructured as an inline
   effect body without duplicating the fetch logic. */
"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

export interface DashboardAnalytics {
  totalProspects: number;
  emailsSent: number;
  callsMade: number;
  replies: number;
  meetingsBooked: number;
  qualificationDistribution: Record<string, number>;
  revenue: {
    estimatedPipelineValue: number;
    meetingValue: number;
    wonValue: number;
    lostValue: number;
  };
  channelPerformance: {
    linkedin: { total: number; replied: number; replyRatePct: number };
    email: { total: number; replied: number; replyRatePct: number };
    call: { total: number; connected: number; connectRatePct: number };
  };
}

interface UseGetAnalyticsReturn {
  data: DashboardAnalytics | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Sprint 6, item 2 (Dashboard Integration): pulls the dashboard's metrics
 * from the real backend analytics endpoints (funnel, outreach, qualification,
 * revenue, channel performance) instead of the hardcoded placeholder numbers
 * the dashboard previously always rendered.
 */
export function useGetAnalytics(): UseGetAnalyticsReturn {
  const [data, setData] = useState<DashboardAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [funnel, outreach, qualification, revenue, channels] = await Promise.all([
        fetchApi("/analytics/metrics/funnel"),
        fetchApi("/analytics/metrics/outreach"),
        fetchApi("/analytics/metrics/qualification"),
        fetchApi("/analytics/metrics/revenue"),
        fetchApi("/analytics/metrics/channel-performance"),
      ]);

      setData({
        totalProspects: funnel.data?.total_prospects ?? 0,
        emailsSent: outreach.data?.currently_in_email_outreach ?? 0,
        callsMade: outreach.data?.currently_in_call_outreach ?? 0,
        replies: outreach.data?.currently_engaged ?? 0,
        meetingsBooked: outreach.data?.meetings_booked ?? 0,
        qualificationDistribution: qualification.data?.qualification_distribution ?? {},
        revenue: {
          estimatedPipelineValue: revenue.data?.estimated_pipeline_value ?? 0,
          meetingValue: revenue.data?.meeting_value ?? 0,
          wonValue: revenue.data?.won_value ?? 0,
          lostValue: revenue.data?.lost_value ?? 0,
        },
        channelPerformance: {
          linkedin: {
            total: channels.data?.linkedin?.total ?? 0,
            replied: channels.data?.linkedin?.replied ?? 0,
            replyRatePct: channels.data?.linkedin?.reply_rate_pct ?? 0,
          },
          email: {
            total: channels.data?.email?.total ?? 0,
            replied: channels.data?.email?.replied ?? 0,
            replyRatePct: channels.data?.email?.reply_rate_pct ?? 0,
          },
          call: {
            total: channels.data?.call?.total ?? 0,
            connected: channels.data?.call?.connected ?? 0,
            connectRatePct: channels.data?.call?.connect_rate_pct ?? 0,
          },
        },
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return { data, loading, error, refetch: fetchData };
}
