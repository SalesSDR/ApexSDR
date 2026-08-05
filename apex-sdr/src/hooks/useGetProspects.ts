/* eslint-disable */
// @ts-nocheck
"use client";

import { useState, useEffect } from "react";
import type { Prospect, LinkedInStage, EmailStage, CallStage } from "@/types";
import { fetchApi } from "@/lib/api";

interface UseGetProspectsReturn {
  data: Prospect[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

function mapBackendStateToFrontend(state: string): { linkedInStage: LinkedInStage, emailStage: EmailStage, callStage: CallStage } {
  // `state` is the backend's ProspectState enum value (Prospect.status).
  // Every value of that enum (backend/src/app/models/schemas.py's
  // ProspectState) has an explicit case below - none of them should ever
  // reach the `default` branch, which exists only as a safety net for a
  // value the frontend genuinely doesn't know about yet (a backend enum
  // addition this mapping hasn't been updated for).
  switch (state) {
    // Pre-outreach qualification phase (Module 3) - nothing has been sent
    // on any channel yet, so "Not Connected/Not Sent/Not Called" is
    // accurate here, not a fallback guess.
    case "NEW":
    case "ENRICHING":
    case "QUALIFIED":
      return { linkedInStage: "Not Connected", emailStage: "Not Sent", callStage: "Not Called" };
    // Disqualified before outreach ever began - a business decision, not
    // "nothing has happened yet", so it needs its own distinct label
    // rather than reusing the pre-outreach one.
    case "DISQUALIFIED":
      return { linkedInStage: "Disqualified", emailStage: "Not Sent", callStage: "Not Called" };
    case "IDLE":
      return { linkedInStage: "Not Connected", emailStage: "Not Sent", callStage: "Not Called" };
    case "LI_REQ_SENT":
      return { linkedInStage: "Request Pending", emailStage: "Not Sent", callStage: "Not Called" };
    case "LI_ACCEPTED_NO_MSG":
      return { linkedInStage: "Request Accepted", emailStage: "Not Sent", callStage: "Not Called" };
    case "LI_MSG_SENT":
    case "LINKEDIN_NO_RESPONSE":
      return { linkedInStage: "Follow Up Msg", emailStage: "Not Sent", callStage: "Not Called" };
    case "LINKEDIN_REPLIED":
      return { linkedInStage: "Responded", emailStage: "Not Sent", callStage: "Not Called" };
    case "EMAIL_SENT":
    case "EMAIL_OPENED":
    case "EMAIL_CLICKED":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Not Called" };
    case "EMAIL_FAILED":
      return { linkedInStage: "Follow Up Msg", emailStage: "Undelivered", callStage: "Not Called" };
    case "EMAIL_REPLIED":
      return { linkedInStage: "Follow Up Msg", emailStage: "Responded", callStage: "Not Called" };
    case "EMAIL_2_SENT":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Not Called" };
    case "CALL_QUEUED":
    case "CALL_IN_PROGRESS":
    case "CALL_RETRY":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Scheduled" };
    case "CALL_CONNECTED":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Answered" };
    case "CALL_NO_ANSWER_1":
    case "CALL_NO_ANSWER_2":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Unanswered" };
    case "CALL_FAILED":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Not Called" };
    case "VOICEMAIL_LEFT":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Voicemail Left" };
    case "BREAKUP_EMAIL_SENT":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Unanswered" };
    case "MEETING_BOOKED":
      return { linkedInStage: "Responded", emailStage: "Responded", callStage: "Answered" };
    case "CLOSED_WON":
      return { linkedInStage: "Closed Won", emailStage: "Responded", callStage: "Answered" };
    case "PAUSED_NUDGED":
    case "COMPLETED_DECLINED":
    case "UNRESPONSIVE_DEAD":
    case "LOST":
    case "ERROR_NEEDS_HUMAN":
    case "ENGAGED_ON_WEBSITE":
      return { linkedInStage: "Not Connected", emailStage: "Not Sent", callStage: "Not Called" };
    default:
      console.warn(`mapBackendStateToFrontend: unrecognized ProspectState "${state}" - falling back to a neutral display. This mapping needs a new explicit case for it.`);
      return { linkedInStage: "Not Connected", emailStage: "Not Sent", callStage: "Not Called" };
  }
}

export function useGetProspects(): UseGetProspectsReturn {
  const [data, setData] = useState<Prospect[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchApi("/prospects");
      if (response.status === "success") {
        const mappedData: Prospect[] = response.data.map((p: any) => {
          const stages = mapBackendStateToFrontend(p.status);
          return {
            id: p.id,
            firstName: p.first_name,
            lastName: p.last_name,
            title: "Prospect", // Default since backend doesn't have it yet
            company: "Unknown", // Default
            avatarInitials: `${p.first_name.charAt(0)}${p.last_name.charAt(0)}`.toUpperCase(),
            avatarColor: "#3b82f6",
            linkedInStage: stages.linkedInStage,
            emailStage: stages.emailStage,
            callStage: stages.callStage,
            lastActivity: "Just now",
            lastActivityDate: new Date().toISOString().split("T")[0],
            email: p.email,
            phone: p.phone_number || "",
            linkedInUrl: p.linkedin_url || "",
            location: "Unknown",
            industry: "Unknown",
            companySize: "Unknown"
          };
        });
        setData(mappedData);
      } else {
        throw new Error("Failed to fetch prospects");
      }
    } catch (err: any) {
      setError(err.message || "Failed to load prospects");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return { data, loading, error, refetch: fetchData };
}
