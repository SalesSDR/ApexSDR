"use client";
import { Header } from "@/components/layout/Header";
import { Search } from "lucide-react";
export default function SearchPage() {
  return (
    <div className="flex flex-col h-full">
      <Header showViewSwitcher={false} showAddProspect={false} />
      <div className="flex-1 flex items-center justify-center" style={{ background: "var(--apex-bg)" }}>
        <div className="text-center">
          <Search size={40} className="mx-auto mb-4" style={{ color: "var(--apex-border)" }} />
          <p className="text-sm font-medium" style={{ color: "var(--apex-text-dim)" }}>Prospect Search</p>
          <p className="text-xs mt-1" style={{ color: "var(--apex-muted)" }}>Coming soon</p>
        </div>
      </div>
    </div>
  );
}
