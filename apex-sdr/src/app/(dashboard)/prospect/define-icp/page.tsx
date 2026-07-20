"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { ICPSidebar } from "@/features/defining-icp/ICPSidebar";
import { ConversationalICPWidget } from "@/features/defining-icp/ConversationalICPWidget";
import { ICPParameterSummary } from "@/features/defining-icp/ICPParameterSummary";
import { ICPWidgetSkeleton, FilterChipSkeleton } from "@/components/ui/Skeletons";
import { useGetICPFilters } from "@/hooks/useGetICPFilters";
import { formatLeadCount } from "@/lib/utils";

export default function DefineICPPage() {
  const { filters, sidebarCategories, conversation, loading, setConversation, setFilters } = useGetICPFilters();

  const handleSendMessage = async (msg: string) => {
    // Optimistically add user message
    const newUserMsg = { id: Date.now().toString(), role: "user" as const, content: msg, timestamp: new Date().toISOString() };
    setConversation((prev) => [...prev, newUserMsg]);
    
    try {
      const response = await fetch("http://localhost:8000/api/v1/icp/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: msg })
      });
      
      const data = await response.json();
      
      if (data.status === "success" && data.filters) {
        const aiResponse = { 
          id: (Date.now() + 1).toString(), 
          role: "assistant" as const, 
          content: `I've analyzed your request and successfully mapped the parameters into structured filters.`,
          timestamp: new Date().toISOString()
        };
        setConversation((prev) => [...prev, aiResponse]);
        
        setFilters(prev => {
          if (!prev) return prev;
          
          const newFilters = { ...prev };
          const categories = ["locations", "jobTitles", "industry", "companySize", "technology", "keywords"] as const;
          
          categories.forEach(cat => {
            if (data.filters[cat] && data.filters[cat].length > 0) {
              newFilters[cat] = [...(prev[cat] || []), ...data.filters[cat]];
            }
          });
          
          return newFilters;
        });
      }
    } catch (error) {
      console.error("Failed to parse ICP query", error);
      const errorMsg = { 
        id: (Date.now() + 1).toString(), 
        role: "assistant" as const, 
        content: `I'm sorry, I encountered an error while trying to process that request.`,
        timestamp: new Date().toISOString()
      };
      setConversation((prev) => [...prev, errorMsg]);
    }
  };

  const handleRemoveChip = (category: keyof typeof filters, value: string) => {
    setFilters((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        [category]: (prev[category] as any[])?.filter((chip: any) => chip.value !== value)
      };
    });
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      <Header
        showResearchButton
        showViewSwitcher
        showAddProspect={false}
        showUploadDownload={false}
      />

      {/* Page body */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* ICP category sidebar — self-contained with full state */}
        <ICPSidebar filters={filters} />

        {/* Main content */}
        <div
          className="flex-1 flex flex-col min-w-0 overflow-y-auto"
          style={{ background: "var(--apex-bg)" }}
        >
          <div className="flex-1 p-5 flex flex-col gap-4 max-w-4xl w-full mx-auto">
            {/* Conversational ICP Widget */}
            {loading ? (
              <ICPWidgetSkeleton />
            ) : (
              <ConversationalICPWidget 
                conversation={conversation} 
                onSendMessage={handleSendMessage}
              />
            )}

            {/* AI-Generated Parameters */}
            {loading ? (
              <div
                className="rounded-xl p-4 space-y-4"
                style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}
              >
                <div className="skeleton h-4 w-48 rounded" />
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex gap-4">
                    <div className="skeleton h-3 w-20 rounded" />
                    <FilterChipSkeleton />
                  </div>
                ))}
              </div>
            ) : filters ? (
              <ICPParameterSummary 
                filters={filters} 
                onRemoveChip={handleRemoveChip as any}
              />
            ) : null}
          </div>

          {/* Footer bar */}
          <div
            className="flex-shrink-0 flex items-center justify-between px-5 py-3"
            style={{
              background: "var(--apex-surface)",
              borderTop: "1px solid var(--apex-border)",
            }}
          >
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs" style={{ color: "var(--apex-muted)" }}>
                Summary of results:
              </span>
              {[
                { label: "Active: Silicon Valley", color: "var(--apex-accent)", bg: "rgba(59,130,246,0.1)", border: "rgba(59,130,246,0.2)" },
                { label: "Company Size parameters", color: "var(--apex-warning)", bg: "rgba(234,179,8,0.1)", border: "rgba(234,179,8,0.2)" },
                { label: "Technology Stack and parameters", color: "var(--apex-gold)", bg: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.2)" },
              ].map((tag) => (
                <span
                  key={tag.label}
                  className="text-xs px-2 py-0.5 rounded-full font-medium"
                  style={{ color: tag.color, background: tag.bg, border: `1px solid ${tag.border}` }}
                >
                  {tag.label}
                </span>
              ))}
            </div>

            <div className="flex items-center gap-3 flex-shrink-0">
              {/* Animated sparkle */}
              <motion.div
                animate={{ rotate: [0, 10, -10, 0], scale: [1, 1.1, 0.95, 1] }}
                transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                style={{ color: "var(--apex-gold)" }}
              >
                <Sparkles size={18} />
              </motion.div>

              {/* Lead counter */}
              <div
                className="flex items-center gap-2 px-4 py-2 rounded-xl"
                style={{
                  background: "rgba(59,130,246,0.08)",
                  border: "1px solid rgba(59,130,246,0.2)",
                }}
              >
                {loading ? (
                  <div className="skeleton h-5 w-24 rounded" />
                ) : (
                  <>
                    <motion.span
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.5 }}
                      className="text-lg font-bold tabular-nums"
                      style={{ color: "var(--apex-accent)" }}
                    >
                      {formatLeadCount(filters?.totalLeads ?? 60902)}
                    </motion.span>
                    <span className="text-xs font-medium" style={{ color: "var(--apex-text-dim)" }}>
                      leads
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
