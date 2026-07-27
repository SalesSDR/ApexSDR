/* eslint-disable */
// @ts-nocheck
"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Bot,
  Users,
  Mail,
  Settings,
  ChevronRight,
  ChevronDown,
  Inbox,
  ListFilter,
  Search,
  Repeat2,
  RefreshCw,
  Zap,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

const SIDEBAR_EXPANDED = 240;
const SIDEBAR_COLLAPSED = 64;

interface SubNavItem {
  id: string;
  label: string;
  href: string;
  icon: React.ReactNode;
}

interface NavSection {
  id: string;
  label: string;
  icon: React.ReactNode;
  href?: string;
  subItems?: SubNavItem[];
}

const navSections: NavSection[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    icon: <LayoutDashboard size={18} />,
    href: "/dashboard",
  },
  {
    id: "ai-copilot",
    label: "AI Co-pilot",
    icon: <Bot size={18} />,
    href: "/ai-copilot",
  },
  {
    id: "prospect",
    label: "Prospect",
    icon: <Users size={18} />,
    subItems: [
      {
        id: "active-queue",
        label: "Active Prospects Queue",
        href: "/prospect/active-queue",
        icon: <Inbox size={14} />,
      },
      {
        id: "engage-queue",
        label: "Engage Queue",
        href: "/prospect/engage-queue",
        icon: <Mail size={14} />,
      },
      {
        id: "define-icp",
        label: "Define ICP",
        href: "/prospect/define-icp",
        icon: <ListFilter size={14} />,
      },
      {
        id: "search",
        label: "Search",
        href: "/prospect/search",
        icon: <Search size={14} />,
      },
      {
        id: "sequences",
        label: "Sequences",
        href: "/prospect/sequences",
        icon: <Repeat2 size={14} />,
      },
      {
        id: "crm-sync",
        label: "CRM Sync",
        href: "/prospect/crm-sync",
        icon: <RefreshCw size={14} />,
      },
    ],
  },
  {
    id: "engage",
    label: "Engage",
    icon: <Zap size={18} />,
    href: "/engage",
  },
  {
    id: "admin-settings",
    label: "Admin Settings",
    icon: <Settings size={18} />,
    href: "/admin-settings",
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [expanded, setExpanded] = useState(true);
  const [expandedSections, setExpandedSections] = useState<string[]>(["prospect"]);
  const [hoverTimeout, setHoverTimeout] = useState<NodeJS.Timeout | null>(null);
  const sidebarRef = useRef<HTMLDivElement>(null);

  const toggleSection = (sectionId: string) => {
    setExpandedSections((prev) =>
      prev.includes(sectionId)
        ? prev.filter((id) => id !== sectionId)
        : [...prev, sectionId]
    );
  };

  const handleMouseEnter = () => {
    if (!expanded) {
      const timeout = setTimeout(() => setExpanded(true), 800);
      setHoverTimeout(timeout);
    }
  };

  const handleMouseLeave = () => {
    if (hoverTimeout) {
      clearTimeout(hoverTimeout);
      setHoverTimeout(null);
    }
  };

  const isActiveSection = (section: NavSection): boolean => {
    if (section.href) return pathname === section.href || pathname.startsWith(section.href);
    if (section.subItems) {
      return section.subItems.some(
        (sub) => pathname === sub.href || pathname.startsWith(sub.href)
      );
    }
    return false;
  };

  const isActiveSubItem = (href: string): boolean =>
    pathname === href || pathname.startsWith(href);

  // Auto-expand "prospect" section if on a prospect page
  useEffect(() => {
    if (pathname.startsWith("/prospect")) {
      setExpandedSections((prev) =>
        prev.includes("prospect") ? prev : [...prev, "prospect"]
      );
    }
  }, [pathname]);

  return (
    <motion.div
      ref={sidebarRef}
      animate={{ width: expanded ? SIDEBAR_EXPANDED : SIDEBAR_COLLAPSED }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      className="flex flex-col h-screen flex-shrink-0 relative z-30"
      style={{
        background: "var(--apex-surface)",
        borderRight: "1px solid var(--apex-border)",
        overflow: "hidden",
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* ── Logo Area ─────────────────────────────────────────── */}
      <div
        className="flex items-center h-14 px-4 flex-shrink-0 relative"
        style={{ borderBottom: "1px solid var(--apex-border)" }}
      >
        {/* Triangle logo icon */}
        <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center">
          <img src="/logo.jpg" alt="Apex Logo" className="w-full h-full object-cover rounded shadow-sm" />
        </div>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2, delay: 0.05 }}
              className="ml-2 flex items-baseline gap-1 whitespace-nowrap"
            >
              <span
                className="text-sm font-bold tracking-tight"
                style={{ color: "var(--apex-text)" }}
              >
                Apex
              </span>
              <span
                className="text-sm font-bold tracking-tight"
                style={{ color: "var(--apex-gold)" }}
              >
                SDR
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Toggle button */}
        <AnimatePresence>
          {expanded && (
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="ml-auto p-1 rounded-md hover:bg-white/5 transition-colors"
              style={{ color: "var(--apex-muted)" }}
              onClick={() => setExpanded(false)}
              aria-label="Collapse sidebar"
            >
              <PanelLeftClose size={15} />
            </motion.button>
          )}
        </AnimatePresence>

        {!expanded && (
          <button
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md hover:bg-white/5 transition-colors"
            style={{ color: "var(--apex-muted)" }}
            onClick={() => setExpanded(true)}
            aria-label="Expand sidebar"
          >
            <PanelLeftOpen size={15} />
          </button>
        )}
      </div>

      {/* ── Navigation ────────────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-3 px-2" aria-label="Main navigation">
        {navSections.map((section) => {
          const isActive = isActiveSection(section);
          const isSectionExpanded = expandedSections.includes(section.id);

          return (
            <div key={section.id} className="mb-0.5">
              {/* Section item */}
              {section.subItems ? (
                <button
                  onClick={() => {
                    if (!expanded) setExpanded(true);
                    toggleSection(section.id);
                  }}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all duration-150 group",
                    isActive
                      ? "text-white"
                      : "hover:bg-white/5"
                  )}
                  style={{
                    background: isActive ? "rgba(59,130,246,0.12)" : undefined,
                    color: isActive ? "var(--apex-accent)" : "var(--apex-text-dim)",
                  }}
                  aria-expanded={isSectionExpanded}
                >
                  <span
                    className="flex-shrink-0 w-5 h-5 flex items-center justify-center"
                    style={{ color: isActive ? "var(--apex-accent)" : "var(--apex-muted)" }}
                  >
                    {section.icon}
                  </span>
                  <AnimatePresence>
                    {expanded && (
                      <motion.span
                        initial={{ opacity: 0, width: 0 }}
                        animate={{ opacity: 1, width: "auto" }}
                        exit={{ opacity: 0, width: 0 }}
                        transition={{ duration: 0.2 }}
                        className="flex-1 text-sm font-medium whitespace-nowrap overflow-hidden"
                      >
                        {section.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                  <AnimatePresence>
                    {expanded && (
                      <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.15 }}
                        style={{ color: "var(--apex-muted)" }}
                      >
                        {isSectionExpanded ? (
                          <ChevronDown size={14} />
                        ) : (
                          <ChevronRight size={14} />
                        )}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </button>
              ) : (
                <Link
                  href={section.href!}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-150",
                    isActive ? "text-white" : "hover:bg-white/5"
                  )}
                  style={{
                    background: isActive ? "rgba(59,130,246,0.12)" : undefined,
                    color: isActive ? "var(--apex-accent)" : "var(--apex-text-dim)",
                  }}
                >
                  <span
                    className="flex-shrink-0 w-5 h-5 flex items-center justify-center"
                    style={{ color: isActive ? "var(--apex-accent)" : "var(--apex-muted)" }}
                  >
                    {section.icon}
                  </span>
                  <AnimatePresence>
                    {expanded && (
                      <motion.span
                        initial={{ opacity: 0, width: 0 }}
                        animate={{ opacity: 1, width: "auto" }}
                        exit={{ opacity: 0, width: 0 }}
                        transition={{ duration: 0.2 }}
                        className="text-sm font-medium whitespace-nowrap overflow-hidden"
                      >
                        {section.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </Link>
              )}

              {/* Sub-items */}
              {section.subItems && (
                <AnimatePresence>
                  {isSectionExpanded && expanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
                      className="overflow-hidden"
                    >
                      <div className="ml-4 mt-0.5 mb-1 pl-3 border-l border-white/10">
                        {section.subItems.map((sub) => {
                          const isSubActive = isActiveSubItem(sub.href);
                          return (
                            <Link
                              key={sub.id}
                              href={sub.href}
                              className={cn(
                                "flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition-all duration-150 my-0.5",
                                isSubActive
                                  ? "font-medium"
                                  : "hover:bg-white/5"
                              )}
                              style={{
                                background: isSubActive
                                  ? "rgba(59,130,246,0.1)"
                                  : undefined,
                                color: isSubActive
                                  ? "var(--apex-accent)"
                                  : "var(--apex-text-faint)",
                              }}
                            >
                              <span style={{ color: isSubActive ? "var(--apex-accent)" : "var(--apex-muted)" }}>
                                {sub.icon}
                              </span>
                              <span className="whitespace-nowrap">{sub.label}</span>
                            </Link>
                          );
                        })}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              )}
            </div>
          );
        })}
      </nav>

      {/* ── Bottom Section ────────────────────────────────────── */}
      <div
        className="flex-shrink-0 px-3 py-3"
        style={{ borderTop: "1px solid var(--apex-border)" }}
      >
        {/* Onboarding Progress */}
        <div
          className={cn(
            "rounded-lg p-3 mb-3 transition-all",
            expanded ? "" : "p-2"
          )}
          style={{ background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.15)" }}
        >
          {expanded ? (
            <>
              <div className="flex items-center justify-between mb-2">
                <span
                  className="text-xs font-medium"
                  style={{ color: "var(--apex-accent)" }}
                >
                  Apex Onboarding
                </span>
                <span className="text-xs" style={{ color: "var(--apex-muted)" }}>
                  40%
                </span>
              </div>
              <div
                className="h-1.5 rounded-full overflow-hidden"
                style={{ background: "rgba(255,255,255,0.1)" }}
              >
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: "40%" }}
                  transition={{ duration: 1, ease: "easeOut", delay: 0.5 }}
                  className="h-full rounded-full"
                  style={{
                    background: "linear-gradient(90deg, #3b82f6, #60a5fa)",
                  }}
                />
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
                style={{
                  background: "conic-gradient(#3b82f6 144deg, rgba(255,255,255,0.1) 144deg)",
                  color: "var(--apex-accent)",
                }}
              >
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
                  style={{ background: "var(--apex-surface)" }}
                >
                  40
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Apex Logo */}
        <div className="flex items-center justify-center gap-2">
          <img src="/logo.jpg" alt="Apex Logo" className="w-5 h-5 object-cover rounded shadow-sm" />
          <AnimatePresence>
            {expanded && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-xs font-semibold tracking-widest uppercase"
                style={{ color: "var(--apex-gold)" }}
              >
                Apex
              </motion.span>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
