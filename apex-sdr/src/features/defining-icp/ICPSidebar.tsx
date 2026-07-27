/* eslint-disable */
// @ts-nocheck
"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Briefcase,
  Users,
  Building2,
  MapPin,
  Tag,
  Cpu,
  ChevronUp,
  ChevronDown,
  Check,
  Search,
  X,
  CircleDot,
  Circle,
  HelpCircle,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ICPFilters } from "@/types";

interface ICPSidebarProps {
  filters?: ICPFilters | null;
}

// ─── Filter Panel Components ──────────────────────────────────────────────────

function RadioOption({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label
      className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg cursor-pointer transition-all hover:bg-white/5 group"
      style={{
        background: checked ? "rgba(59,130,246,0.1)" : undefined,
        border: checked ? "1px solid rgba(59,130,246,0.25)" : "1px solid transparent",
      }}
      onClick={onChange}
    >
      <div
        className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 transition-all"
        style={{
          border: `2px solid ${checked ? "var(--apex-accent)" : "var(--apex-border)"}`,
          background: checked ? "var(--apex-accent)" : "transparent",
        }}
      >
        {checked && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
      </div>
      <span
        className="text-xs transition-colors"
        style={{ color: checked ? "var(--apex-text)" : "var(--apex-text-dim)" }}
      >
        {label}
      </span>
    </label>
  );
}

function CheckOption({
  label,
  checked,
  onChange,
  dimmed,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
  dimmed?: boolean;
}) {
  return (
    <label
      className="flex items-center gap-2.5 px-3 py-2 rounded-md cursor-pointer transition-all hover:bg-white/5"
      style={{ opacity: dimmed ? 0.5 : 1 }}
      onClick={onChange}
    >
      <div
        className="w-3.5 h-3.5 rounded-sm flex items-center justify-center flex-shrink-0 transition-all"
        style={{
          background: checked ? "var(--apex-accent)" : "rgba(255,255,255,0.05)",
          border: `1px solid ${checked ? "var(--apex-accent)" : "var(--apex-border)"}`,
        }}
      >
        {checked && <Check size={9} color="white" strokeWidth={3} />}
      </div>
      <span className="text-xs" style={{ color: "var(--apex-text-dim)" }}>
        {label}
      </span>
    </label>
  );
}

function TagInput({
  placeholder,
  tags,
  onAddTag,
  onRemoveTag,
}: {
  placeholder: string;
  tags: string[];
  onAddTag: (tag: string) => void;
  onRemoveTag: (tag: string) => void;
}) {
  const [input, setInput] = useState("");
  const [focused, setFocused] = useState(false);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.key === "Enter" || e.key === ",") && input.trim()) {
      e.preventDefault();
      onAddTag(input.trim());
      setInput("");
    }
    if (e.key === "Backspace" && !input && tags.length > 0) {
      onRemoveTag(tags[tags.length - 1]);
    }
  };

  return (
    <div
      className="min-h-[38px] px-2.5 py-1.5 rounded-lg flex flex-wrap items-center gap-1.5 cursor-text transition-all"
      style={{
        background: "var(--apex-surface-2)",
        border: `1px solid ${focused ? "var(--apex-accent)" : "var(--apex-border)"}`,
        boxShadow: focused ? "0 0 0 2px rgba(59,130,246,0.1)" : undefined,
      }}
      onClick={() => document.getElementById(`tag-input-${placeholder}`)?.focus()}
    >
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs"
          style={{
            background: "rgba(59,130,246,0.15)",
            color: "var(--apex-accent)",
            border: "1px solid rgba(59,130,246,0.25)",
          }}
        >
          {tag}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemoveTag(tag);
            }}
            className="hover:opacity-70 transition-opacity"
            aria-label={`Remove ${tag}`}
          >
            <X size={9} />
          </button>
        </span>
      ))}
      <input
        id={`tag-input-${placeholder}`}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        className="flex-1 min-w-[80px] bg-transparent text-xs focus:outline-none placeholder:opacity-40"
        style={{ color: "var(--apex-text-dim)" }}
        placeholder={tags.length === 0 ? placeholder : ""}
        aria-label={placeholder}
      />
    </div>
  );
}

// ─── Filter Panels per Category ───────────────────────────────────────────────

function JobTitlesPanel({ filters, tags, setTags }: { filters?: ICPFilters | null, tags: string[], setTags: React.Dispatch<React.SetStateAction<string[]>> }) {
  const [mode, setMode] = useState<"is-any-of" | "is-known" | "is-unknown">("is-any-of");
  const [includeManagement, setIncludeManagement] = useState(false);
  const [excludeSenior, setExcludeSenior] = useState(false);

  // Sync with global filters
  useEffect(() => {
    if (filters?.jobTitles) {
      setTags(filters.jobTitles.map(t => t.label));
    }
  }, [filters, setTags]);

  return (
    <div className="space-y-1 pb-1">
      <RadioOption
        label="Is any of"
        checked={mode === "is-any-of"}
        onChange={() => setMode("is-any-of")}
      />
      <AnimatePresence>
        {mode === "is-any-of" && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden px-3 pb-2"
          >
            <TagInput
              placeholder="e.g. VP of Sales, Director..."
              tags={tags}
              onAddTag={(t) => setTags((p) => [...p, t])}
              onRemoveTag={(t) => setTags((p) => p.filter((x) => x !== t))}
            />
            <div className="mt-2 space-y-0.5">
              <CheckOption
                label="Include management-level titles"
                checked={includeManagement}
                onChange={() => setIncludeManagement((v) => !v)}
              />
              <CheckOption
                label="Exclude senior-level variations"
                checked={excludeSenior}
                onChange={() => setExcludeSenior((v) => !v)}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <RadioOption
        label="Is not any of"
        checked={false}
        onChange={() => {}}
      />
      <RadioOption
        label="Is known"
        checked={mode === "is-known"}
        onChange={() => setMode("is-known")}
      />
      <RadioOption
        label="Is unknown"
        checked={mode === "is-unknown"}
        onChange={() => setMode("is-unknown")}
      />
    </div>
  );
}

function PeopleLookalikesPanel({ tags, setTags }: { tags: string[], setTags: React.Dispatch<React.SetStateAction<string[]>> }) {
  return (
    <div className="space-y-2 px-3 pb-3">
      <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
        Find contacts similar to existing prospects or customers.
      </p>
      <TagInput
        placeholder="Enter LinkedIn URLs or names..."
        tags={tags}
        onAddTag={(t) => setTags((p) => [...p, t])}
        onRemoveTag={(t) => setTags((p) => p.filter((x) => x !== t))}
      />
      <div className="flex items-center gap-1.5 text-xs" style={{ color: "var(--apex-muted)" }}>
        <HelpCircle size={11} />
        <span>Paste a LinkedIn profile URL or full name</span>
      </div>
    </div>
  );
}

function CompanyPanel({ tags, setTags }: { tags: string[], setTags: React.Dispatch<React.SetStateAction<string[]>> }) {
  const [mode, setMode] = useState<"is-any-of" | "is-known" | "is-unknown">("is-any-of");
  const [isNotAnyOf, setIsNotAnyOf] = useState(false);
  const [includePast, setIncludePast] = useState(false);
  const [excludePast, setExcludePast] = useState(false);
  const [domainExists, setDomainExists] = useState(false);

  return (
    <div className="space-y-1 pb-1">
      <RadioOption
        label="Is any of"
        checked={mode === "is-any-of"}
        onChange={() => setMode("is-any-of")}
      />
      <AnimatePresence>
        {mode === "is-any-of" && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden px-3 pb-2"
          >
            <TagInput
              placeholder="Enter companies..."
              tags={tags}
              onAddTag={(t) => setTags((p) => [...p, t])}
              onRemoveTag={(t) => setTags((p) => p.filter((x) => x !== t))}
            />
            <div className="mt-2 space-y-0.5">
              <CheckOption label="Is not any of" checked={isNotAnyOf} onChange={() => setIsNotAnyOf((v) => !v)} />
              <CheckOption label="Include past company" checked={includePast} onChange={() => setIncludePast((v) => !v)} />
              <CheckOption label="Exclude past company" checked={excludePast} onChange={() => setExcludePast((v) => !v)} />
              <CheckOption label="Domain exists" checked={domainExists} onChange={() => setDomainExists((v) => !v)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <RadioOption label="Is known" checked={mode === "is-known"} onChange={() => setMode("is-known")} />
      <RadioOption label="Is unknown" checked={mode === "is-unknown"} onChange={() => setMode("is-unknown")} />
    </div>
  );
}

function LocationPanel({ filters, locationTags, setLocationTags }: { filters?: ICPFilters | null, locationTags: string[], setLocationTags: React.Dispatch<React.SetStateAction<string[]>> }) {
  const [tab, setTab] = useState<"contact" | "account-hq">("contact");
  const [mode, setMode] = useState<"region" | "zip-radius">("region");
  const [showExclude, setShowExclude] = useState(false);
  const [excludeTags, setExcludeTags] = useState<string[]>([]);


  useEffect(() => {
    if (filters?.locations) {
      setLocationTags(filters.locations.map(t => t.label));
    }
  }, [filters, setLocationTags]);

  return (
    <div className="space-y-2 pb-2">
      {/* Tabs */}
      <div
        className="flex mx-3 rounded-lg overflow-hidden"
        style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)" }}
      >
        {[
          { id: "contact" as const, label: "Contact" },
          { id: "account-hq" as const, label: "Account HQ" },
        ].map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className="flex-1 py-1.5 text-xs font-medium transition-all"
            style={{
              background: tab === id ? "var(--apex-surface-3)" : "transparent",
              color: tab === id ? "var(--apex-text)" : "var(--apex-muted)",
              borderBottom: tab === id ? "1px solid var(--apex-accent)" : "1px solid transparent",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <RadioOption label="Select region" checked={mode === "region"} onChange={() => setMode("region")} />
      <AnimatePresence>
        {mode === "region" && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden px-3 pb-1"
          >
            <p className="text-xs font-medium mb-1.5" style={{ color: "var(--apex-text-dim)" }}>
              City / State / Country / ZIP
            </p>
            <TagInput
              placeholder="Enter locations..."
              tags={locationTags}
              onAddTag={(t) => setLocationTags((p) => [...p, t])}
              onRemoveTag={(t) => setLocationTags((p) => p.filter((x) => x !== t))}
            />
            <button
              onClick={() => setShowExclude((v) => !v)}
              className="flex items-center gap-1 mt-2 text-xs font-medium transition-colors hover:opacity-80"
              style={{ color: "var(--apex-accent)" }}
            >
              Exclude locations
              <ChevronDown size={11} className={cn("transition-transform", showExclude && "rotate-180")} />
            </button>
            <AnimatePresence>
              {showExclude && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden mt-2"
                >
                  <TagInput
                    placeholder="Enter locations to exclude..."
                    tags={excludeTags}
                    onAddTag={(t) => setExcludeTags((p) => [...p, t])}
                    onRemoveTag={(t) => setExcludeTags((p) => p.filter((x) => x !== t))}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
      <RadioOption label="Select ZIP code radius" checked={mode === "zip-radius"} onChange={() => setMode("zip-radius")} />
    </div>
  );
}

function IndustryKeywordsPanel({ filters, keywordTags, setKeywordTags }: { filters?: ICPFilters | null, keywordTags: string[], setKeywordTags: React.Dispatch<React.SetStateAction<string[]>> }) {
  const [includeKeywords, setIncludeKeywords] = useState(true);
  const [includeAll, setIncludeAll] = useState(false);
  const [excludeKeywords, setExcludeKeywords] = useState(false);
  const [excludeTags, setExcludeTags] = useState<string[]>([]);


  useEffect(() => {
    if (filters?.keywords) {
      setKeywordTags(filters.keywords.map(t => t.label));
    }
  }, [filters, setKeywordTags]);

  return (
    <div className="space-y-1 pb-1">
      <div
        className="mx-3 mb-2 px-3 py-2 rounded-lg"
        style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)" }}
      >
        <CheckOption
          label="Include keywords"
          checked={includeKeywords}
          onChange={() => setIncludeKeywords((v) => !v)}
        />
        <AnimatePresence>
          {includeKeywords && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden mt-2"
            >
              <TagInput
                placeholder="e.g. Cloud, AWS"
                tags={keywordTags}
                onAddTag={(t) => setKeywordTags((p) => [...p, t])}
                onRemoveTag={(t) => setKeywordTags((p) => p.filter((x) => x !== t))}
              />
              <button
                className="flex items-center gap-1 mt-1.5 text-xs font-medium transition-colors"
                style={{ color: "var(--apex-accent)" }}
              >
                Type of Keywords
                <ChevronDown size={10} />
                <AlertTriangle size={10} style={{ color: "var(--apex-warning)", marginLeft: 2 }} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <CheckOption label="Include ALL" checked={includeAll} onChange={() => setIncludeAll((v) => !v)} />

      <div
        className="mx-3 p-3 rounded-lg space-y-2"
        style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)" }}
      >
        <CheckOption
          label="Exclude keywords"
          checked={excludeKeywords}
          onChange={() => setExcludeKeywords((v) => !v)}
        />
        <AnimatePresence>
          {excludeKeywords && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <TagInput
                placeholder="e.g. Agency, Consulting"
                tags={excludeTags}
                onAddTag={(t) => setExcludeTags((p) => [...p, t])}
                onRemoveTag={(t) => setExcludeTags((p) => p.filter((x) => x !== t))}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <p className="px-3 text-xs mt-1" style={{ color: "var(--apex-muted)" }}>
        Keywords filters may slow down your search.
      </p>
    </div>
  );
}

function TechnologyStackPanel({ filters, tags, setTags }: { filters?: ICPFilters | null, tags: string[], setTags: React.Dispatch<React.SetStateAction<string[]>> }) {
  const [mode, setMode] = useState<"is-any-of" | "is-known" | "is-unknown">("is-any-of");

  useEffect(() => {
    if (filters?.technology) {
      setTags(filters.technology.map(t => t.label));
    }
  }, [filters, setTags]);

  return (
    <div className="space-y-1 pb-1">
      <RadioOption label="Uses any of" checked={mode === "is-any-of"} onChange={() => setMode("is-any-of")} />
      <AnimatePresence>
        {mode === "is-any-of" && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden px-3 pb-2"
          >
            <TagInput
              placeholder="e.g. HubSpot, Salesforce..."
              tags={tags}
              onAddTag={(t) => setTags((p) => [...p, t])}
              onRemoveTag={(t) => setTags((p) => p.filter((x) => x !== t))}
            />
          </motion.div>
        )}
      </AnimatePresence>
      <RadioOption label="Does not use" checked={false} onChange={() => {}} />
      <RadioOption label="Is known" checked={mode === "is-known"} onChange={() => setMode("is-known")} />
      <RadioOption label="Is unknown" checked={mode === "is-unknown"} onChange={() => setMode("is-unknown")} />
    </div>
  );
}

// ─── Category Config ──────────────────────────────────────────────────────────

interface CategoryConfig {
  id: string;
  label: string;
  icon: React.ReactNode;
  panel: (filters?: ICPFilters | null) => React.ReactNode;
  activeCount?: number;
}

// ─── Main ICPSidebar ──────────────────────────────────────────────────────────

interface ICPSidebarProps {
  filters?: ICPFilters | null;
  onApplyFilters?: (prompt: string) => void;
}

export function ICPSidebar({ filters, onApplyFilters }: ICPSidebarProps) {
  const [openCategory, setOpenCategory] = useState<string>("job-titles");
  
  // Lifted state
  const [jobTitles, setJobTitles] = useState<string[]>([]);
  const [peopleLookalikes, setPeopleLookalikes] = useState<string[]>([]);
  const [companies, setCompanies] = useState<string[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [technologies, setTechnologies] = useState<string[]>([]);

  const CATEGORIES = [
    {
      id: "job-titles",
      label: "Job Titles",
      icon: <Briefcase size={14} />,
      panel: (filters: ICPFilters | null | undefined) => <JobTitlesPanel filters={filters} tags={jobTitles} setTags={setJobTitles} />,
      activeCount: jobTitles.length > 0 ? jobTitles.length : undefined,
    },
    {
      id: "people-lookalikes",
      label: "People Lookalikes",
      icon: <Users size={14} />,
      panel: () => <PeopleLookalikesPanel tags={peopleLookalikes} setTags={setPeopleLookalikes} />,
      activeCount: peopleLookalikes.length > 0 ? peopleLookalikes.length : undefined,
    },
    {
      id: "company",
      label: "Company",
      icon: <Building2 size={14} />,
      panel: () => <CompanyPanel tags={companies} setTags={setCompanies} />,
      activeCount: companies.length > 0 ? companies.length : undefined,
    },
    {
      id: "location",
      label: "Location",
      icon: <MapPin size={14} />,
      panel: (filters: ICPFilters | null | undefined) => <LocationPanel filters={filters} locationTags={locations} setLocationTags={setLocations} />,
      activeCount: locations.length > 0 ? locations.length : undefined,
    },
    {
      id: "industry-keywords",
      label: "Industry & Keywords",
      icon: <Tag size={14} />,
      panel: (filters: ICPFilters | null | undefined) => <IndustryKeywordsPanel filters={filters} keywordTags={keywords} setKeywordTags={setKeywords} />,
      activeCount: keywords.length > 0 ? keywords.length : undefined,
    },
    {
      id: "technology-stack",
      label: "Technology Stack",
      icon: <Cpu size={14} />,
      panel: (filters: ICPFilters | null | undefined) => <TechnologyStackPanel filters={filters} tags={technologies} setTags={setTechnologies} />,
      activeCount: technologies.length > 0 ? technologies.length : undefined,
    },
  ];

  const toggle = (id: string) => {
    setOpenCategory((prev) => (prev === id ? "" : id));
  };
  
  const handleApply = () => {
    if (!onApplyFilters) return;
    const parts = [];
    if (jobTitles.length > 0) parts.push(`Job Titles: [${jobTitles.join(", ")}]`);
    if (companies.length > 0) parts.push(`Companies: [${companies.join(", ")}]`);
    if (locations.length > 0) parts.push(`Locations: [${locations.join(", ")}]`);
    if (keywords.length > 0) parts.push(`Keywords: [${keywords.join(", ")}]`);
    if (technologies.length > 0) parts.push(`Tech Stack: [${technologies.join(", ")}]`);
    if (peopleLookalikes.length > 0) parts.push(`Lookalikes: [${peopleLookalikes.join(", ")}]`);
    
    if (parts.length === 0) {
      onApplyFilters("Find a general list of prospects.");
    } else {
      onApplyFilters(`Find prospects with ${parts.join(", ")}`);
    }
  };

  return (
    <div
      className="w-64 flex-shrink-0 flex flex-col overflow-hidden"
      style={{
        borderRight: "1px solid var(--apex-border)",
        background: "var(--apex-surface)",
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center gap-2"
        style={{ borderBottom: "1px solid var(--apex-border)" }}
      >
        <Search size={13} style={{ color: "var(--apex-muted)" }} />
        <input
          className="flex-1 bg-transparent text-xs focus:outline-none placeholder:opacity-40"
          style={{ color: "var(--apex-text-dim)" }}
          placeholder="Search filters..."
          aria-label="Search ICP filters"
        />
      </div>

      {/* Categories accordion */}
      <div className="flex-1 overflow-y-auto py-1">
        {CATEGORIES.map((cat) => {
          const isOpen = openCategory === cat.id;
          return (
            <div key={cat.id}>
              {/* Category header */}
              <button
                onClick={() => toggle(cat.id)}
                className="w-full flex items-center justify-between px-4 py-2.5 transition-all hover:bg-white/5 group"
                style={{
                  background: isOpen ? "rgba(59,130,246,0.06)" : undefined,
                  borderLeft: isOpen
                    ? "2px solid var(--apex-accent)"
                    : "2px solid transparent",
                }}
                aria-expanded={isOpen}
                id={`icp-filter-${cat.id}`}
              >
                <div className="flex items-center gap-2.5">
                  <span
                    className="transition-colors"
                    style={{ color: isOpen ? "var(--apex-accent)" : "var(--apex-muted)" }}
                  >
                    {cat.icon}
                  </span>
                  <span
                    className="text-xs font-medium transition-colors"
                    style={{ color: isOpen ? "var(--apex-text)" : "var(--apex-text-dim)" }}
                  >
                    {cat.label}
                  </span>
                  {cat.activeCount && (
                    <span
                      className="text-xs px-1.5 py-0.5 rounded-full font-medium"
                      style={{
                        background: "rgba(59,130,246,0.15)",
                        color: "var(--apex-accent)",
                      }}
                    >
                      {cat.activeCount}
                    </span>
                  )}
                </div>
                <span
                  className="transition-colors"
                  style={{ color: isOpen ? "var(--apex-accent)" : "var(--apex-muted)" }}
                >
                  {isOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                </span>
              </button>

              {/* Expanded filter panel */}
              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    key={cat.id + "-panel"}
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
                    className="overflow-hidden"
                    style={{
                      background: "var(--apex-surface-2)",
                      borderBottom: "1px solid var(--apex-border)",
                    }}
                  >
                    <div className="py-2">{cat.panel(filters)}</div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Separator */}
              <div style={{ height: 1, background: "var(--apex-border)", opacity: 0.5 }} />
            </div>
          );
        })}
      </div>

      {/* Advanced Filters footer */}
      <div
        className="px-4 py-3 flex-shrink-0 flex flex-col gap-2"
        style={{ borderTop: "1px solid var(--apex-border)" }}
      >
        <button
          onClick={handleApply}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition-colors"
        >
          <Search size={14} /> Apply Filters
        </button>
        <button
          className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-white/5 transition-colors"
          style={{ color: "var(--apex-muted)", border: "1px solid var(--apex-border)" }}
        >
          <span className="text-xs">Advanced Filters</span>
          <span
            className="text-xs px-1.5 py-0.5 rounded"
            style={{
              background: "rgba(59,130,246,0.12)",
              color: "var(--apex-accent)",
            }}
          >
            Pro
          </span>
        </button>
      </div>
    </div>
  );
}
