"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, X, Send, AlertCircle } from "lucide-react";
import { CHAT_WEBHOOK_URL } from "@/lib/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type Role = "user" | "agent";
type MessageStatus = "sent" | "sending" | "error";

interface ChatMessage {
  id: string;
  role: Role;
  text: string;
  status?: MessageStatus;
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function generateId(): string {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);
}

// ---------------------------------------------------------------------------
// Typing indicator dots component
// ---------------------------------------------------------------------------
function TypingDots() {
  return (
    <div className="flex items-center gap-1 px-4 py-3">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-gray-400"
          style={{
            animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toast notification component
// ---------------------------------------------------------------------------
function ToastNotification({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 4000);
    return () => clearTimeout(t);
  }, [onDismiss]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.95 }}
      className="absolute bottom-16 right-0 w-72 bg-[#1A1A1A] border border-[#E5D5C5]/30 rounded-xl shadow-2xl px-4 py-3 flex items-start gap-3"
    >
      <div className="w-7 h-7 rounded-full bg-[#E5D5C5] flex items-center justify-center text-black font-bold text-xs flex-none mt-0.5">
        A
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-white mb-0.5">Apex replied</p>
        <p className="text-xs text-gray-400 truncate">{message}</p>
      </div>
      <button
        onClick={onDismiss}
        className="text-gray-500 hover:text-white flex-none mt-0.5"
      >
        <X size={14} />
      </button>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Main Widget
// ---------------------------------------------------------------------------
export function AskApexWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: generateId(),
      role: "agent",
      text: "Hi! I'm Apex. How can I help you scale your outbound pipeline today?",
      timestamp: Date.now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [toast, setToast] = useState<string | null>(null);
  const [sessionId] = useState<string>(() => generateId());

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastAgentMsgRef = useRef<number>(Date.now());

  // Scroll to the latest message
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      setUnreadCount(0);
    }
  }, [messages, isOpen, scrollToBottom]);

  // -------------------------------------------------------------------------
  // Add an agent message and trigger notification if widget is closed
  // -------------------------------------------------------------------------
  const addAgentMessage = useCallback(
    (text: string) => {
      const msg: ChatMessage = {
        id: generateId(),
        role: "agent",
        text,
        timestamp: Date.now(),
      };
      lastAgentMsgRef.current = msg.timestamp;
      setMessages((prev) => [...prev, msg]);
      setIsTyping(false);

      if (!isOpen) {
        setUnreadCount((c) => c + 1);
        setToast(text);
      }
    },
    [isOpen]
  );

  // -------------------------------------------------------------------------
  // Poll for reply (GET ?session_id=xxx) after a message is sent.
  // Retries up to 5 times with 3s intervals. Stops if a response arrives.
  // -------------------------------------------------------------------------
  const startPolling = useCallback(
    (afterTimestamp: number) => {
      let attempts = 0;
      const MAX_ATTEMPTS = 5;
      const INTERVAL_MS = 3000;

      const poll = async () => {
        if (attempts >= MAX_ATTEMPTS) {
          setIsTyping(false);
          return;
        }
        attempts++;
        try {
          const res = await fetch(
            `${CHAT_WEBHOOK_URL}?session_id=${sessionId}&after=${afterTimestamp}`
          );
          if (res.ok) {
            const data = await res.json();
            // Accept either { reply } or { message } from backend / n8n
            const replyText: string | undefined =
              data?.reply || data?.message || data?.response;
            if (replyText) {
              addAgentMessage(replyText);
              return; // Stop polling — we got a reply
            }
          }
        } catch {
          // Network error — silently retry
        }
        // Schedule next poll
        pollTimerRef.current = setTimeout(poll, INTERVAL_MS);
      };

      pollTimerRef.current = setTimeout(poll, INTERVAL_MS);
    },
    [sessionId, addAgentMessage]
  );

  // Cleanup poll timer on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, []);

  // -------------------------------------------------------------------------
  // Send message handler
  // -------------------------------------------------------------------------
  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isTyping) return;

    const sentAt = Date.now();
    const userMsg: ChatMessage = {
      id: generateId(),
      role: "user",
      text,
      status: "sending",
      timestamp: sentAt,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    // Clear any in-progress poll
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);

    try {
      const res = await fetch(CHAT_WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message_text: text,
          timestamp: new Date(sentAt).toISOString(),
          metadata: {
            source: "marketing_site",
            user_agent:
              typeof navigator !== "undefined" ? navigator.userAgent : "unknown",
          },
        }),
      });

      // Mark the user message as sent
      setMessages((prev) =>
        prev.map((m) =>
          m.id === userMsg.id ? { ...m, status: "sent" } : m
        )
      );

      if (res.ok) {
        const data = await res.json();
        // If backend returns a synchronous reply, show it immediately
        const directReply: string | undefined =
          data?.reply || data?.message || data?.response;
        if (directReply) {
          addAgentMessage(directReply);
          return;
        }
      }
    } catch {
      // Mark as error if network fails
      setMessages((prev) =>
        prev.map((m) =>
          m.id === userMsg.id ? { ...m, status: "error" } : m
        )
      );
      setIsTyping(false);
      addAgentMessage(
        "Sorry, I couldn't connect to the backend right now. Please try again shortly."
      );
      return;
    }

    // No synchronous reply — start polling for async response
    startPolling(sentAt);
  }, [input, isTyping, sessionId, addAgentMessage, startPolling]);

  const handleOpen = () => {
    setIsOpen(true);
    setUnreadCount(0);
    setToast(null);
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {/* Toast notification (shown when widget is closed) */}
      <AnimatePresence>
        {!isOpen && toast && (
          <ToastNotification
            message={toast}
            onDismiss={() => setToast(null)}
          />
        )}
      </AnimatePresence>

      {/* Chat Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="mb-4 w-80 bg-[#1A1A1A] border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col h-[420px]"
          >
            {/* Header */}
            <div className="bg-[#E5D5C5] text-black px-4 py-3 flex items-center justify-between flex-none">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-black flex items-center justify-center text-white font-bold text-xs">
                  A
                </div>
                <div>
                  <h4 className="font-semibold text-sm">Ask Apex</h4>
                  <div className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-600 inline-block" />
                    <p className="text-xs opacity-80">Online</p>
                  </div>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 hover:bg-black/10 rounded-full transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                      msg.role === "user"
                        ? "bg-[#E5D5C5] text-black rounded-tr-sm"
                        : "bg-white/10 text-white rounded-tl-sm"
                    }`}
                  >
                    {msg.text}
                    {/* Sending / error status indicator */}
                    {msg.role === "user" && msg.status === "sending" && (
                      <span className="block text-[10px] opacity-50 mt-1 text-right">
                        Sending…
                      </span>
                    )}
                    {msg.role === "user" && msg.status === "error" && (
                      <span className="flex items-center gap-1 justify-end text-[10px] text-red-500 mt-1">
                        <AlertCircle size={10} /> Failed
                      </span>
                    )}
                  </div>
                </div>
              ))}

              {/* Agent typing indicator */}
              {isTyping && (
                <div className="flex justify-start">
                  <div className="bg-white/10 rounded-2xl rounded-tl-sm">
                    <TypingDots />
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-3 border-t border-white/10 bg-black flex-none">
              <div className="relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  placeholder="Ask a question…"
                  disabled={isTyping}
                  className="w-full bg-white/5 border border-white/10 rounded-full py-2 pl-4 pr-10 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-white/30 transition-colors disabled:opacity-50"
                />
                <button
                  onClick={handleSend}
                  disabled={isTyping || !input.trim()}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-white text-black rounded-full hover:bg-gray-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Send size={14} />
                </button>
              </div>
              <p className="text-[10px] text-gray-600 text-center mt-2">
                Powered by Apex SDR AI
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toggle Button with unread badge */}
      <button
        onClick={isOpen ? () => setIsOpen(false) : handleOpen}
        className="w-14 h-14 bg-[#E5D5C5] text-black rounded-full flex items-center justify-center shadow-2xl hover:scale-105 transition-transform relative"
        aria-label={isOpen ? "Close chat" : "Open chat"}
      >
        {isOpen ? <X size={24} /> : <MessageSquare size={24} />}

        {/* Unread badge */}
        <AnimatePresence>
          {!isOpen && unreadCount > 0 && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0 }}
              className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center shadow"
            >
              {unreadCount > 9 ? "9+" : unreadCount}
            </motion.span>
          )}
        </AnimatePresence>
      </button>
    </div>
  );
}
