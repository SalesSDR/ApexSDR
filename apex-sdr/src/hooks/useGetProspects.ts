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
  switch (state) {
    case "IDLE":
      return { linkedInStage: "Not Connected", emailStage: "Not Sent", callStage: "Not Called" };
    case "LI_REQ_SENT":
      return { linkedInStage: "Request Pending", emailStage: "Not Sent", callStage: "Not Called" };
    case "LI_ACCEPTED_NO_MSG":
      return { linkedInStage: "Request Accepted", emailStage: "Not Sent", callStage: "Not Called" };
    case "LI_MSG_SENT":
    case "LINKEDIN_NO_RESPONSE":
      return { linkedInStage: "Follow Up Msg", emailStage: "Not Sent", callStage: "Not Called" };
    case "EMAIL_SENT":
    case "EMAIL_OPENED":
    case "EMAIL_CLICKED":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Not Called" };
    case "EMAIL_FAILED":
      return { linkedInStage: "Follow Up Msg", emailStage: "Undelivered", callStage: "Not Called" };
    case "CALL_QUEUED":
    case "CALL_IN_PROGRESS":
    case "CALL_RETRY":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Scheduled" };
    case "CALL_NO_ANSWER_1":
    case "CALL_NO_ANSWER_2":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Unanswered" };
    case "CALL_FAILED":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Not Called" };
    case "MEETING_BOOKED":
      return { linkedInStage: "Responded", emailStage: "Responded", callStage: "Answered" };
    case "PAUSED_NUDGED":
    case "COMPLETED_DECLINED":
    case "UNRESPONSIVE_DEAD":
    case "LOST":
    case "ERROR_NEEDS_HUMAN":
    case "ENGAGED_ON_WEBSITE":
      return { linkedInStage: "Not Connected", emailStage: "Not Sent", callStage: "Not Called" };
    default:
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
