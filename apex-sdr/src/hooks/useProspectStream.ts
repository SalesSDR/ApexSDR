/* eslint-disable */
// @ts-nocheck
"use client";

import { useEffect } from "react";
import { API_BASE_URL, getAuthCredential } from "@/lib/api";

export function useProspectStream(onEvent: (data: any) => void) {
  useEffect(() => {
    // EventSource cannot set an Authorization header, so the credential
    // travels as a query param here only - every other endpoint sends it
    // via the Authorization header (see lib/api.ts#fetchApi).
    const credential = getAuthCredential();
    if (!credential) {
      console.warn("No auth credential configured; skipping prospect stream connection.");
      return;
    }
    const url = `${API_BASE_URL}/prospects/stream?token=${encodeURIComponent(credential)}`;
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
      if (eventSource.readyState === EventSource.CLOSED) {
        console.warn("SSE connection closed by server. Browser will auto-reconnect.");
      }
    };

    return () => {
      eventSource.close();
    };
  }, [onEvent]);
}
