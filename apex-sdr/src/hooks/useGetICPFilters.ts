"use client";

import { useState } from "react";
import type { ICPFilters, ICPSidebarCategory, ChatMessage } from "@/types";

interface UseGetICPFiltersReturn {
  filters: ICPFilters | null;
  sidebarCategories: ICPSidebarCategory[];
  conversation: ChatMessage[];
  loading: boolean;
  error: string | null;
  setFilters: React.Dispatch<React.SetStateAction<ICPFilters | null>>;
  setConversation: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
}

/**
 * Sprint 7.1: there is no backend endpoint for "the tenant's saved ICP
 * filters" or "prior ICP chat history" - only the stateless /icp/parse and
 * /icp/preview endpoints (see api/v1/icp.py). Rather than fabricate that
 * data client-side, this starts from a genuinely empty state: no filters
 * defined yet, no invented conversation history. The define-icp page's
 * real conversation (handleSendMessage -> /icp/preview, via the
 * authenticated fetchApi client) populates `conversation` as the user
 * actually interacts.
 */
export function useGetICPFilters(): UseGetICPFiltersReturn {
  const [filters, setFilters] = useState<ICPFilters | null>(null);
  const [sidebarCategories] = useState<ICPSidebarCategory[]>([]);
  const [conversation, setConversation] = useState<ChatMessage[]>([]);

  return {
    filters,
    sidebarCategories,
    conversation,
    loading: false,
    error: null,
    setFilters,
    setConversation,
  };
}
