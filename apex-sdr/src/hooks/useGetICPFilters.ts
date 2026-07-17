"use client";

import { useState, useEffect } from "react";
import type { ICPFilters, ICPSidebarCategory, ChatMessage } from "@/types";
import icpData from "@/mocks/icpFilters.json";

interface UseGetICPFiltersReturn {
  filters: ICPFilters | null;
  sidebarCategories: ICPSidebarCategory[];
  conversation: ChatMessage[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
  setFilters: React.Dispatch<React.SetStateAction<ICPFilters | null>>;
  setConversation: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
}

export function useGetICPFilters(): UseGetICPFiltersReturn {
  const [filters, setFilters] = useState<ICPFilters | null>(null);
  const [sidebarCategories, setSidebarCategories] = useState<ICPSidebarCategory[]>([]);
  const [conversation, setConversation] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = () => {
    setLoading(true);
    setError(null);
    setTimeout(() => {
      try {
        const { sidebarCategories: cats, conversationHistory, ...filterData } = icpData as any;
        setFilters(filterData as ICPFilters);
        setSidebarCategories(cats as ICPSidebarCategory[]);
        setConversation(conversationHistory as ChatMessage[]);
      } catch (err) {
        setError("Failed to load ICP filters");
      } finally {
        setLoading(false);
      }
    }, 400);
  };

  useEffect(() => {
    fetchData();
  }, []);

  return { filters, sidebarCategories, conversation, loading, error, refetch: fetchData, setFilters, setConversation };
}
