/* eslint-disable */
// @ts-nocheck
"use client";
import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Search, Users, Link as LinkIcon, Building2, Briefcase, Plus, Check } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { toast } from "sonner";

interface ApolloProfile {
  id: string;
  first_name: string;
  last_name: string;
  name: string;
  linkedin_url: string | null;
  title: string | null;
  organization?: {
    name: string;
  };
  contact?: {
    linkedin_url?: string;
  };
  email: string | null;
}

export default function SearchPage() {
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [results, setResults] = useState<ApolloProfile[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async () => {
    setLoading(true);
    setHasSearched(true);
    try {
      // Hardcode a basic query for demo, ideally this would pull from the ICP Builder Context
      const payload = {
        person_titles: ["software engineer", "founder", "CEO", "CTO", "VP Engineering"],
        person_locations: ["United States", "San Francisco"],
        q_organization_domains: "",
        page: 1,
        per_page: 50
      };

      const data = await fetchApi("/apollo/search", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      if (data.people) {
        setResults(data.people);
      }
    } catch (error) {
      console.error(error);
      toast.error("Failed to fetch from Apollo");
    } finally {
      setLoading(false);
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
    if (selectedIds.size === results.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(results.map(r => r.id)));
    }
  };

  const handleImport = async () => {
    if (selectedIds.size === 0) return;
    setImporting(true);

    const profilesToImport = results
      .filter(r => selectedIds.has(r.id))
      .map(r => ({
        first_name: r.first_name,
        last_name: r.last_name,
        title: r.title,
        organization_name: r.organization?.name || "",
        email: r.email || `placeholder_${r.id}@example.com`,
        linkedin_url: r.linkedin_url || r.contact?.linkedin_url || ""
      }));

    try {
      const data = await fetchApi("/prospects/import-from-apollo", {
        method: "POST",
        body: JSON.stringify({ profiles: profilesToImport })
      });

      if (data.status === "success") {
        toast.success(`Imported ${data.imported} prospects to pipeline. Skipped ${data.skipped} duplicates.`);
        setSelectedIds(new Set());
        // Remove imported from view
        setResults(prev => prev.filter(p => !selectedIds.has(p.id)));
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
    <div className="flex flex-col h-full bg-[#0A0A0A] text-white overflow-hidden">
      <Header showViewSwitcher={false} showAddProspect={false} />
      
      {/* Top Action Bar */}
      <div className="flex-shrink-0 p-4 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button 
            onClick={handleSearch}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
          >
            {loading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Search size={16} />}
            Search Apollo Live Data
          </button>
          
          <span className="text-xs text-neutral-400">
            Applying ICP Filters: "US", "Engineering/Founders"
          </span>
        </div>

        <button 
          onClick={handleImport}
          disabled={selectedIds.size === 0 || importing}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
        >
          {importing ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Plus size={16} />}
          Add {selectedIds.size} to Sequence
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {!hasSearched ? (
          <div className="flex flex-col items-center justify-center h-full text-neutral-500">
            <Users size={48} className="mb-4 opacity-20" />
            <p>Click search to query live B2B data matching your ICP</p>
          </div>
        ) : loading ? (
          <div className="space-y-4">
            {[...Array(10)].map((_, i) => (
              <div key={i} className="h-16 bg-white/5 animate-pulse rounded-xl border border-white/10" />
            ))}
          </div>
        ) : results.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-neutral-500">
            <p>No results found for current filters.</p>
          </div>
        ) : (
          <div className="bg-[#111111] border border-white/10 rounded-xl overflow-hidden shadow-xl">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-neutral-400 uppercase bg-white/5 border-b border-white/10">
                <tr>
                  <th className="p-4 w-12">
                    <input 
                      type="checkbox" 
                      className="rounded bg-white/10 border-white/20"
                      checked={selectedIds.size === results.length && results.length > 0}
                      onChange={selectAll}
                    />
                  </th>
                  <th className="p-4">Name</th>
                  <th className="p-4">Title</th>
                  <th className="p-4">Company</th>
                  <th className="p-4">LinkedIn URL</th>
                  <th className="p-4">Email Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {results.map(person => {
                  const isSelected = selectedIds.has(person.id);
                  const liUrl = person.linkedin_url || person.contact?.linkedin_url;
                  
                  return (
                    <tr 
                      key={person.id} 
                      className={`hover:bg-white/5 transition-colors ${isSelected ? 'bg-blue-500/10' : ''}`}
                    >
                      <td className="p-4">
                        <input 
                          type="checkbox" 
                          className="rounded bg-white/10 border-white/20"
                          checked={isSelected}
                          onChange={() => toggleSelection(person.id)}
                        />
                      </td>
                      <td className="p-4 font-medium text-white">{person.name}</td>
                      <td className="p-4 text-neutral-300">
                        <div className="flex items-center gap-2">
                          <Briefcase size={14} className="text-neutral-500" />
                          {person.title || "—"}
                        </div>
                      </td>
                      <td className="p-4 text-neutral-300">
                        <div className="flex items-center gap-2">
                          <Building2 size={14} className="text-neutral-500" />
                          {person.organization?.name || "—"}
                        </div>
                      </td>
                      <td className="p-4">
                        {liUrl ? (
                          <a href={liUrl} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline flex items-center gap-1">
                            <LinkIcon size={14} /> Profile
                          </a>
                        ) : (
                          <span className="text-neutral-600">—</span>
                        )}
                      </td>
                      <td className="p-4">
                        {person.email ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            <Check size={12} /> Verified
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-neutral-500/10 text-neutral-400 border border-neutral-500/20">
                            Missing
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
