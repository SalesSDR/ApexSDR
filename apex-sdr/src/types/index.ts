// ─── Prospect & CRM Types ────────────────────────────────────────────────────

export type LinkedInStage =
  | "Request Accepted"
  | "Request Pending"
  | "Responded"
  | "Follow Up Msg"
  | "Not Connected"
  | "Connection Sent"
  | "Disqualified"
  | "Closed Won";

export type EmailStage =
  | "Email Sent"
  | "Delivered"
  | "Undelivered"
  | "Responded"
  | "Bounced"
  | "Not Sent";

export type CallStage =
  | "Answered"
  | "Unanswered"
  | "Spoke to gatekeeper"
  | "Responded"
  | "Scheduled"
  | "Not Called"
  | "Voicemail Left";

export interface CallSummary {
  date: string;
  duration: string;
  summary: string;
  nextStep: string;
}

export interface Prospect {
  id: string;
  firstName: string;
  lastName: string;
  title: string;
  company: string;
  companyLogo?: string;
  avatarInitials: string;
  avatarColor: string;
  linkedInStage: LinkedInStage;
  emailStage: EmailStage;
  callStage: CallStage;
  callSummary?: CallSummary;
  lastActivity: string;
  lastActivityDate: string;
  email: string;
  phone: string;
  linkedInUrl: string;
  location: string;
  industry: string;
  companySize: string;
  selected?: boolean;
}

// ─── ICP Filter Types ─────────────────────────────────────────────────────────

export interface ICPFilterChip {
  label: string;
  value: string;
  removable?: boolean;
}

export interface ICPFilterCategory {
  id: string;
  label: string;
  icon?: string;
  chips: ICPFilterChip[];
  expanded?: boolean;
}

export interface ICPFilters {
  locations: ICPFilterChip[];
  jobTitles: ICPFilterChip[];
  industry: ICPFilterChip[];
  companySize: ICPFilterChip[];
  revenue: ICPFilterChip[];
  technology: ICPFilterChip[];
  keywords: ICPFilterChip[];
  totalLeads: number;
}

export interface ICPSidebarCategory {
  id: string;
  label: string;
  count?: number;
  items?: { label: string; count: string; selected?: boolean }[];
  expanded?: boolean;
}

// ─── Onboarding Types ─────────────────────────────────────────────────────────

export interface OnboardingStep {
  id: string;
  label: string;
  completed: boolean;
  description: string;
}

export interface OnboardingStatus {
  progress: number;
  currentStep: string;
  steps: OnboardingStep[];
  label: string;
}

// ─── Navigation Types ─────────────────────────────────────────────────────────

export type NavItemId =
  | "dashboard"
  | "ai-copilot"
  | "prospect"
  | "engage"
  | "admin-settings";

export interface NavSubItem {
  id: string;
  label: string;
  href: string;
  badge?: string;
}

export interface NavItem {
  id: NavItemId;
  label: string;
  icon: string;
  href?: string;
  subItems?: NavSubItem[];
}

// ─── UI State Types ───────────────────────────────────────────────────────────

export interface UIState {
  sidebarExpanded: boolean;
  activeRoute: string;
  selectedProspects: string[];
  onboardingProgress: number;
  viewMode: "list" | "grid" | "card";
}

// ─── Chat / AI Types ──────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface AIConversation {
  messages: ChatMessage[];
  isThinking: boolean;
}
