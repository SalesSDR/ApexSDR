/* eslint-disable */
// @ts-nocheck
"use client";

import { useState } from "react";
import { fetchApi } from "@/lib/api";
import { X, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface AddProspectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function AddProspectModal({ isOpen, onClose, onSuccess }: AddProspectModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    const formData = new FormData(e.currentTarget);
    const data = {
      first_name: formData.get("firstName") as string,
      last_name: formData.get("lastName") as string,
      email: formData.get("email") as string,
      linkedin_url: formData.get("linkedinUrl") as string,
      phone_number: (formData.get("phone") as string) || undefined,
    };
    
    try {
      await fetchApi("/prospects", {
        method: "POST",
        body: JSON.stringify(data),
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to add prospect");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="relative w-full max-w-md rounded-xl p-6 shadow-2xl"
            style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold" style={{ color: "var(--apex-text)" }}>
                Add New Prospect
              </h2>
              <button
                onClick={onClose}
                className="p-1 rounded-lg hover:bg-white/5 transition-colors"
                style={{ color: "var(--apex-muted)" }}
              >
                <X size={18} />
              </button>
            </div>
            
            {error && (
              <div className="mb-4 p-3 rounded-lg text-sm bg-red-500/10 text-red-400 border border-red-500/20">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium" style={{ color: "var(--apex-text-dim)" }}>
                    First Name
                  </label>
                  <input
                    required
                    name="firstName"
                    className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                    style={{ background: "var(--apex-surface-2)", color: "var(--apex-text)", border: "1px solid var(--apex-border)" }}
                    placeholder="Jane"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium" style={{ color: "var(--apex-text-dim)" }}>
                    Last Name
                  </label>
                  <input
                    required
                    name="lastName"
                    className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                    style={{ background: "var(--apex-surface-2)", color: "var(--apex-text)", border: "1px solid var(--apex-border)" }}
                    placeholder="Doe"
                  />
                </div>
              </div>
              
              <div className="space-y-1.5">
                <label className="text-xs font-medium" style={{ color: "var(--apex-text-dim)" }}>
                  Email Address
                </label>
                <input
                  required
                  type="email"
                  name="email"
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ background: "var(--apex-surface-2)", color: "var(--apex-text)", border: "1px solid var(--apex-border)" }}
                  placeholder="jane.doe@example.com"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium" style={{ color: "var(--apex-text-dim)" }}>
                  LinkedIn Profile URL
                </label>
                <input
                  required
                  type="url"
                  name="linkedinUrl"
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ background: "var(--apex-surface-2)", color: "var(--apex-text)", border: "1px solid var(--apex-border)" }}
                  placeholder="https://linkedin.com/in/janedoe"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium" style={{ color: "var(--apex-text-dim)" }}>
                  Phone Number (Optional)
                </label>
                <input
                  type="tel"
                  name="phone"
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ background: "var(--apex-surface-2)", color: "var(--apex-text)", border: "1px solid var(--apex-border)" }}
                  placeholder="+14155550101"
                />
              </div>

              <div className="pt-4 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-lg text-sm font-medium transition-colors hover:bg-white/5"
                  style={{ color: "var(--apex-text-dim)" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-lg text-sm font-semibold transition-all flex items-center gap-2"
                  style={{ background: "var(--apex-accent)", color: "white" }}
                >
                  {loading && <Loader2 size={14} className="animate-spin" />}
                  Add Prospect
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
