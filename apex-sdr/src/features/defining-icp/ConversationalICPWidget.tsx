"use client";

import { useState, useRef } from "react";
import { motion } from "framer-motion";
import { Send, Sparkles, X, Bot } from "lucide-react";
import type { ChatMessage } from "@/types";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "Decision makers at Series C SaaS",
  "Fintech leads in London",
  "Companies using Marketo",
];

interface ConversationalICPWidgetProps {
  conversation: ChatMessage[];
  onClose?: () => void;
  onSendMessage?: (msg: string) => void;
  className?: string;
}

export function ConversationalICPWidget({
  conversation,
  onClose,
  onSendMessage,
  className,
}: ConversationalICPWidgetProps) {
  const [inputValue, setInputValue] = useState(
    "Show me VPs of Marketing at B2B tech companies in the US with 500+ employees, based in Silicon Valley, that use HubSpot."
  );
  const [isTyping, setIsTyping] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!inputValue.trim()) return;
    
    if (onSendMessage) {
      onSendMessage(inputValue);
    }
    
    setInputValue("");
    setIsTyping(true);
    setTimeout(() => setIsTyping(false), 2000);
  };

  const handleSuggestion = (text: string) => {
    setInputValue(text);
    inputRef.current?.focus();
  };

  return (
    <div
      className={cn("rounded-xl overflow-hidden flex flex-col", className)}
      style={{
        background: "var(--apex-surface)",
        border: "1px solid var(--apex-border)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
      }}
    >
      {/* Widget Header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: "1px solid var(--apex-border)" }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{ background: "rgba(59,130,246,0.15)" }}
          >
            <Sparkles size={13} style={{ color: "var(--apex-accent)" }} className="sparkle-animate" />
          </div>
          <span className="text-xs font-semibold" style={{ color: "var(--apex-text)" }}>
            Conversational ICP Builder
          </span>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-white/5 transition-colors"
            style={{ color: "var(--apex-muted)" }}
            aria-label="Close ICP builder"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* Conversation area */}
      <div className="flex-1 px-4 py-3 space-y-3 min-h-0">
        {/* Previous messages */}
        {conversation.map((msg) => (
          <div key={msg.id} className={cn("flex gap-2.5", msg.role === "user" ? "justify-end" : "justify-start")}>
            {msg.role === "assistant" && (
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                style={{ background: "rgba(245,158,11,0.15)" }}
              >
                <Bot size={12} style={{ color: "var(--apex-gold)" }} />
              </div>
            )}
            <div
              className="max-w-[80%] rounded-xl px-3 py-2"
              style={{
                background:
                  msg.role === "user"
                    ? "rgba(59,130,246,0.12)"
                    : "var(--apex-surface-2)",
                border: `1px solid ${msg.role === "user" ? "rgba(59,130,246,0.2)" : "var(--apex-border)"}`,
                color: msg.role === "user" ? "var(--apex-text)" : "var(--apex-text-dim)",
              }}
            >
              {msg.role === "assistant" && (
                <span
                  className="text-xs font-semibold block mb-0.5"
                  style={{ color: "var(--apex-gold)" }}
                >
                  Apex SDR:
                </span>
              )}
              <p className="text-xs leading-relaxed">{msg.content}</p>
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {isTyping && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-2.5"
          >
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ background: "rgba(245,158,11,0.15)" }}
            >
              <Bot size={12} style={{ color: "var(--apex-gold)" }} />
            </div>
            <div
              className="rounded-xl px-4 py-3 flex items-center gap-1"
              style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)" }}
            >
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ background: "var(--apex-muted)" }}
                  animate={{ opacity: [0.4, 1, 0.4], y: [0, -3, 0] }}
                  transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15 }}
                />
              ))}
            </div>
          </motion.div>
        )}
      </div>

      {/* Suggestion chips */}
      <div className="px-4 pb-3 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => handleSuggestion(s)}
            className="px-2.5 py-1 rounded-full text-xs transition-all hover:scale-105"
            style={{
              background: "var(--apex-surface-2)",
              border: "1px solid var(--apex-border)",
              color: "var(--apex-text-dim)",
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Input Area */}
      <div
        className="px-4 pb-4"
        style={{ borderTop: "1px solid var(--apex-border)", paddingTop: 12 }}
      >
        <div
          className="flex items-end gap-2 rounded-xl p-3"
          style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)" }}
        >
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            className="flex-1 bg-transparent resize-none text-xs leading-relaxed focus:outline-none"
            style={{ color: "var(--apex-text-dim)", minHeight: 36, maxHeight: 100 }}
            placeholder="Describe your ideal customer profile..."
            rows={2}
            aria-label="ICP query input"
          />
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleSend}
            className="p-2 rounded-lg flex-shrink-0 transition-all"
            style={{
              background: "var(--apex-accent)",
              color: "white",
            }}
            aria-label="Send ICP query"
            id="icp-send-btn"
          >
            <Send size={13} />
          </motion.button>
        </div>
      </div>
    </div>
  );
}
