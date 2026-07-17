"use client";

import { useEffect } from "react";
import { API_BASE_URL, TENANT_ID } from "@/lib/api";

export function useProspectStream(onEvent: (data: any) => void) {
  useEffect(() => {
    const url = `${API_BASE_URL}/prospects/stream?tenant_id=${TENANT_ID}`;
    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onEvent(data);
      } catch (err) {
        console.error("Failed to parse SSE event data:", err);
      }
    };

    eventSource.onerror = (err) => {
      console.error("EventSource failed:", err);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [onEvent]);
}
