"use client";

import { cn } from "@/lib/utils";
import type { LinkedInStage, EmailStage, CallStage } from "@/types";
import {
  CheckCircle2,
  Clock,
  MessageSquare,
  Reply,
  Send,
  MailCheck,
  MailX,
  Phone,
  PhoneOff,
  PhoneCall,
  UserCheck,
  UserPlus,
  UserX,
  Link2,
  Trophy,
  Voicemail,
} from "lucide-react";

type StageVariant = "linkedin" | "email" | "call";

interface StageChipProps {
  stage: LinkedInStage | EmailStage | CallStage;
  variant: StageVariant;
  className?: string;
}

const linkedInConfig: Record<LinkedInStage, { color: string; bg: string; border: string; icon: React.ReactNode }> = {
  "Request Accepted": {
    color: "#22c55e",
    bg: "rgba(34,197,94,0.1)",
    border: "rgba(34,197,94,0.2)",
    icon: <UserCheck size={11} />,
  },
  "Request Pending": {
    color: "#eab308",
    bg: "rgba(234,179,8,0.1)",
    border: "rgba(234,179,8,0.2)",
    icon: <Clock size={11} />,
  },
  Responded: {
    color: "#3b82f6",
    bg: "rgba(59,130,246,0.1)",
    border: "rgba(59,130,246,0.2)",
    icon: <Reply size={11} />,
  },
  "Follow Up Msg": {
    color: "#a855f7",
    bg: "rgba(168,85,247,0.1)",
    border: "rgba(168,85,247,0.2)",
    icon: <MessageSquare size={11} />,
  },
  "Not Connected": {
    color: "#64748b",
    bg: "rgba(100,116,139,0.1)",
    border: "rgba(100,116,139,0.2)",
    icon: <Link2 size={11} />,
  },
  "Connection Sent": {
    color: "#06b6d4",
    bg: "rgba(6,182,212,0.1)",
    border: "rgba(6,182,212,0.2)",
    icon: <UserPlus size={11} />,
  },
  Disqualified: {
    color: "#ef4444",
    bg: "rgba(239,68,68,0.1)",
    border: "rgba(239,68,68,0.2)",
    icon: <UserX size={11} />,
  },
  "Closed Won": {
    color: "#16a34a",
    bg: "rgba(22,163,74,0.1)",
    border: "rgba(22,163,74,0.2)",
    icon: <Trophy size={11} />,
  },
};

const emailConfig: Record<EmailStage, { color: string; bg: string; border: string; icon: React.ReactNode }> = {
  "Email Sent": {
    color: "#3b82f6",
    bg: "rgba(59,130,246,0.1)",
    border: "rgba(59,130,246,0.2)",
    icon: <Send size={11} />,
  },
  Delivered: {
    color: "#22c55e",
    bg: "rgba(34,197,94,0.1)",
    border: "rgba(34,197,94,0.2)",
    icon: <MailCheck size={11} />,
  },
  Undelivered: {
    color: "#ef4444",
    bg: "rgba(239,68,68,0.1)",
    border: "rgba(239,68,68,0.2)",
    icon: <MailX size={11} />,
  },
  Responded: {
    color: "#22c55e",
    bg: "rgba(34,197,94,0.1)",
    border: "rgba(34,197,94,0.2)",
    icon: <Reply size={11} />,
  },
  Bounced: {
    color: "#ef4444",
    bg: "rgba(239,68,68,0.1)",
    border: "rgba(239,68,68,0.2)",
    icon: <MailX size={11} />,
  },
  "Not Sent": {
    color: "#64748b",
    bg: "rgba(100,116,139,0.1)",
    border: "rgba(100,116,139,0.2)",
    icon: <Send size={11} />,
  },
};

const callConfig: Record<CallStage, { color: string; bg: string; border: string; icon: React.ReactNode }> = {
  Answered: {
    color: "#22c55e",
    bg: "rgba(34,197,94,0.1)",
    border: "rgba(34,197,94,0.2)",
    icon: <Phone size={11} />,
  },
  Unanswered: {
    color: "#64748b",
    bg: "rgba(100,116,139,0.1)",
    border: "rgba(100,116,139,0.2)",
    icon: <PhoneOff size={11} />,
  },
  "Spoke to gatekeeper": {
    color: "#eab308",
    bg: "rgba(234,179,8,0.1)",
    border: "rgba(234,179,8,0.2)",
    icon: <PhoneCall size={11} />,
  },
  Responded: {
    color: "#3b82f6",
    bg: "rgba(59,130,246,0.1)",
    border: "rgba(59,130,246,0.2)",
    icon: <Reply size={11} />,
  },
  Scheduled: {
    color: "#a855f7",
    bg: "rgba(168,85,247,0.1)",
    border: "rgba(168,85,247,0.2)",
    icon: <CheckCircle2 size={11} />,
  },
  "Not Called": {
    color: "#64748b",
    bg: "rgba(100,116,139,0.1)",
    border: "rgba(100,116,139,0.2)",
    icon: <Phone size={11} />,
  },
  "Voicemail Left": {
    color: "#8b5cf6",
    bg: "rgba(139,92,246,0.1)",
    border: "rgba(139,92,246,0.2)",
    icon: <Voicemail size={11} />,
  },
};

export function StageChip({ stage, variant, className }: StageChipProps) {
  let config:
    | (typeof linkedInConfig)[LinkedInStage]
    | (typeof emailConfig)[EmailStage]
    | (typeof callConfig)[CallStage]
    | undefined;

  if (variant === "linkedin") config = linkedInConfig[stage as LinkedInStage];
  else if (variant === "email") config = emailConfig[stage as EmailStage];
  else if (variant === "call") config = callConfig[stage as CallStage];

  if (!config) return null;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap",
        className
      )}
      style={{
        color: config.color,
        background: config.bg,
        border: `1px solid ${config.border}`,
      }}
    >
      {config.icon}
      {stage}
    </span>
  );
}
