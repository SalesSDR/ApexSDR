"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Calendar, ArrowRight, Clock } from "lucide-react";
import type { CallSummary } from "@/types";
import { cn } from "@/lib/utils";

interface CallSummaryPopoverProps {
  callSummary: CallSummary;
  className?: string;
}

export function CallSummaryPopover({ callSummary, className }: CallSummaryPopoverProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        !triggerRef.current?.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <div className={cn("relative inline-flex", className)}>
      <button
        ref={triggerRef}
        onClick={() => setOpen(!open)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={(e) => {
          // Keep open if hovering popover
          if (!popoverRef.current?.contains(e.relatedTarget as Node)) {
            setOpen(false);
          }
        }}
        className="p-1 rounded-md transition-all hover:scale-110"
        style={{
          color: "#a855f7",
          background: "rgba(168,85,247,0.12)",
          border: "1px solid rgba(168,85,247,0.2)",
        }}
        aria-label="View call summary"
        aria-expanded={open}
        id="call-summary-trigger"
      >
        <FileText size={12} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            ref={popoverRef}
            initial={{ opacity: 0, y: 6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.96 }}
            transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
            className="absolute z-50 w-72 rounded-xl p-4 left-0 top-8"
            style={{
              background: "var(--apex-surface-2)",
              border: "1px solid var(--apex-border)",
              boxShadow: "0 20px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(168,85,247,0.1)",
            }}
            onMouseEnter={() => setOpen(true)}
            onMouseLeave={() => setOpen(false)}
          >
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
              <div
                className="p-1.5 rounded-lg"
                style={{ background: "rgba(168,85,247,0.15)", color: "#a855f7" }}
              >
                <FileText size={13} />
              </div>
              <div>
                <p className="text-xs font-semibold" style={{ color: "var(--apex-text)" }}>
                  Call Summary
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="flex items-center gap-1 text-xs" style={{ color: "var(--apex-muted)" }}>
                    <Calendar size={10} />
                    {callSummary.date}
                  </span>
                  <span className="flex items-center gap-1 text-xs" style={{ color: "var(--apex-muted)" }}>
                    <Clock size={10} />
                    {callSummary.duration}
                  </span>
                </div>
              </div>
            </div>

            {/* Divider */}
            <div className="h-px mb-3" style={{ background: "var(--apex-border)" }} />

            {/* Summary text */}
            <p className="text-xs leading-relaxed mb-3" style={{ color: "var(--apex-text-dim)" }}>
              {callSummary.summary}
            </p>

            {/* Next step */}
            <div
              className="flex items-start gap-2 p-2.5 rounded-lg"
              style={{ background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.15)" }}
            >
              <ArrowRight size={12} className="mt-0.5 flex-shrink-0" style={{ color: "var(--apex-accent)" }} />
              <p className="text-xs" style={{ color: "var(--apex-accent)" }}>
                {callSummary.nextStep}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
