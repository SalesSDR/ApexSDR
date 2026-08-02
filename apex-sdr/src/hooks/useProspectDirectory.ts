"use client";

import useSWR from "swr";
import { fetchApi } from "@/lib/api";

export interface DirectoryProspect {
  id: string;
  name: string;
  email: string;
  status: string;
}

export function useProspectDirectory() {
  const { data, error, isLoading } = useSWR("/prospects", fetchApi);

  const prospects: DirectoryProspect[] = (data?.data ?? []).map((p: Record<string, string>) => ({
    id: p.id,
    name: `${p.first_name} ${p.last_name}`.trim(),
    email: p.email,
    status: p.status,
  }));

  const byId = new Map(prospects.map((p) => [p.id, p]));

  return {
    prospects,
    byId,
    isLoading,
    error: error ? (error instanceof Error ? error.message : "Failed to load prospects") : null,
  };
}
