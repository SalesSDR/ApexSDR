"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Sparkles, Users, Building2, Briefcase, Link as LinkIcon, Plus, Check } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { ICPSidebar } from "@/features/defining-icp/ICPSidebar";
import { ConversationalICPWidget } from "@/features/defining-icp/ConversationalICPWidget";
import { ICPWidgetSkeleton } from "@/components/ui/Skeletons";
import { useGetICPFilters } from "@/hooks/useGetICPFilters";
import { API_BASE_URL } from "@/lib/config";
import { toast } from "sonner";

interface PreviewLead {
  id: string;
  first_name: string;
  last_name: string;
  title: string;
  company: string;
  linkedin_url: string;
  email: string;
}

export default function DefineICPPage() {
  const { filters, loading, conversation, setConversation } = useGetICPFilters();
  const [leads, setLeads] = useState<PreviewLead[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [fetchingPreview, setFetchingPreview] = useState(false);
  const [importing, setImporting] = useState(false);

  const handleSendMessage = async (msg: string) => {
    // Optimistically add user message
    const newUserMsg = { id: Date.now().toString(), role: "user" as const, content: msg, timestamp: new Date().toISOString() };
    setConversation((prev) => [...prev, newUserMsg]);
    
    setFetchingPreview(true);
    try {
      const response = await fetch(`${API_BASE_URL}/icp/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: msg })
      });
      
      const data = await response.json();
      
      if (data.status === "success" && data.leads) {
        const aiResponse = { 
          id: (Date.now() + 1).toString(), 
          role: "assistant" as const, 
          content: `I've mapped your query to Unipile parameters and fetched the live LinkedIn data. Here is a live preview of the target prospects.`,
          timestamp: new Date().toISOString()
        };
        setConversation((prev) => [...prev, aiResponse]);
        setLeads(data.leads);
        // Auto-select all by default
        setSelectedIds(new Set(data.leads.map((l: PreviewLead) => l.id)));
      } else {
        throw new Error(data.detail || "Failed to fetch preview");
      }
    } catch (error: any) {
      console.error("Failed to fetch ICP preview", error);
      const errorMsg = { 
        id: (Date.now() + 1).toString(), 
        role: "assistant" as const, 
        content: `I encountered an error fetching live data: ${error.message}`,
        timestamp: new Date().toISOString()
      };
      setConversation((prev) => [...prev, errorMsg]);
    } finally {
      setFetchingPreview(false);
    }
  };

  const toggleSelection = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (selectedIds.size === leads.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(leads.map(l => l.id)));
    }
  };

  const handleApprove = async () => {
    if (selectedIds.size === 0) return;
    setImporting(true);

    const profilesToImport = leads
      .filter(l => selectedIds.has(l.id))
      .map(l => ({
        provider_id: l.id,
        first_name: l.first_name,
        last_name: l.last_name,
        title: l.title,
        organization_name: l.company,
        email: l.email || `placeholder_${l.id}@example.com`,
        linkedin_url: l.linkedin_url
      }));

    try {
      const res = await fetch(`${API_BASE_URL}/prospects/import-from-unipile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profiles: profilesToImport })
      });
      const data = await res.json();
      
      if (data.status === "success") {
        toast.success(`Imported ${data.imported} prospects to pipeline. Skipped ${data.skipped} duplicates.`);
        setSelectedIds(new Set());
        setLeads(prev => prev.filter(p => !selectedIds.has(p.id)));
      } else {
        toast.error("Failed to import prospects");
      }
    } catch (e) {
      toast.error("Import failed");
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#0A0A0A] text-white">
      <Header showResearchButton showViewSwitcher showAddProspect={false} showUploadDownload={false} />

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <ICPSidebar filters={filters} onApplyFilters={handleSendMessage} />

        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto p-5">
          <div className="max-w-6xl w-full mx-auto grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
            
            {/* Left Column: Chat */}
            <div className="flex flex-col h-[600px] border border-white/10 bg-[#111] rounded-xl overflow-hidden shadow-xl">
              <div className="p-4 border-b border-white/10 bg-white/5 font-medium flex items-center gap-2">
                <Sparkles size={16} className="text-blue-400" />
                Conversational ICP Builder
              </div>
              <div className="flex-1 overflow-hidden flex flex-col">
                {loading ? (
                  <div className="p-4"><ICPWidgetSkeleton /></div>
                ) : (
                  <ConversationalICPWidget 
                    conversation={conversation} 
                    onSendMessage={handleSendMessage}
                  />
                )}
              </div>
            </div>

            {/* Right Column: Preview Data */}
            <div className="flex flex-col h-[600px] border border-white/10 bg-[#111] rounded-xl overflow-hidden shadow-xl">
              <div className="p-4 border-b border-white/10 bg-white/5 font-medium flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users size={16} className="text-emerald-400" />
                  Live Data Preview (Unipile LinkedIn Search)
                </div>
                {leads.length > 0 && (
                  <button 
                    onClick={handleApprove}
                    disabled={selectedIds.size === 0 || importing}
                    className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    {importing ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Plus size={14} />}
                    Approve & Start Sequence
                  </button>
                )}
              </div>
              
              <div className="flex-1 overflow-y-auto bg-black/20">
                {fetchingPreview ? (
                  <div className="p-6 space-y-4">
                    <div className="flex items-center justify-center gap-2 text-blue-400 mb-6">
                      <Sparkles size={16} className="animate-pulse" />
                      Parsing intent & fetching live data...
                    </div>
                    {[...Array(6)].map((_, i) => (
                      <div key={i} className="h-16 bg-white/5 animate-pulse rounded-xl border border-white/10" />
                    ))}
                  </div>
                ) : leads.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-neutral-500 p-6 text-center">
                    <Users size={48} className="mb-4 opacity-20" />
                    <p>Tell the AI what you're looking for to preview live matching prospects from LinkedIn via Unipile.</p>
                  </div>
                ) : (
                  <table className="w-full text-sm text-left">
                    <thead className="text-xs text-neutral-400 uppercase bg-white/5 border-b border-white/10 sticky top-0">
                      <tr>
                        <th className="p-3 w-10">
                          <input 
                            type="checkbox" 
                            className="rounded bg-white/10 border-white/20"
                            checked={selectedIds.size === leads.length && leads.length > 0}
                            onChange={selectAll}
                          />
                        </th>
                        <th className="p-3">Prospect</th>
                        <th className="p-3">Role & Company</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {leads.map(person => {
                        const isSelected = selectedIds.has(person.id);
                        return (
                          <tr 
                            key={person.id} 
                            className={`hover:bg-white/5 transition-colors ${isSelected ? 'bg-blue-500/5' : ''}`}
                          >
                            <td className="p-3">
                              <input 
                                type="checkbox" 
                                className="rounded bg-white/10 border-white/20"
                                checked={isSelected}
                                onChange={() => toggleSelection(person.id)}
                              />
                            </td>
                            <td className="p-3">
                              <div className="font-medium text-white">{person.first_name} {person.last_name}</div>
                              <div className="flex items-center gap-2 mt-1">
                                {person.linkedin_url ? (
                                  <a href={person.linkedin_url} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline flex items-center gap-1 text-xs">
                                    <LinkIcon size={12} /> Profile
                                  </a>
                                ) : (
                                  <span className="text-neutral-600 text-xs">—</span>
                                )}
                                {person.email && (
                                  <span className="text-emerald-400 text-xs flex items-center gap-1">
                                    <Check size={12} /> Email
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="p-3">
                              <div className="flex items-center gap-2 text-neutral-300">
                                <Briefcase size={14} className="text-neutral-500 flex-shrink-0" />
                                <span className="truncate">{person.title || "—"}</span>
                              </div>
                              <div className="flex items-center gap-2 text-neutral-400 mt-1">
                                <Building2 size={14} className="text-neutral-500 flex-shrink-0" />
                                <span className="truncate">{person.company || "—"}</span>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
