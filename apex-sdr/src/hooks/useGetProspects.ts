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
  switch (state) {
    case "PROSPECT_CREATED":
      return { linkedInStage: "Not Connected", emailStage: "Not Sent", callStage: "Not Called" };
    case "PENDING_ACCEPTANCE":
      return { linkedInStage: "Request Pending", emailStage: "Not Sent", callStage: "Not Called" };
    case "CONNECTION_ACCEPTED":
      return { linkedInStage: "Request Accepted", emailStage: "Not Sent", callStage: "Not Called" };
    case "INITIAL_MSG_SENT":
    case "WAITING_FOR_REPLY":
      return { linkedInStage: "Follow Up Msg", emailStage: "Not Sent", callStage: "Not Called" };
    case "EMAIL_QUEUED":
      return { linkedInStage: "Not Connected", emailStage: "Not Sent", callStage: "Not Called" };
    case "EMAIL_SENT":
      return { linkedInStage: "Not Connected", emailStage: "Email Sent", callStage: "Not Called" };
    case "EMAIL_FAILED":
      return { linkedInStage: "Not Connected", emailStage: "Undelivered", callStage: "Not Called" };
    case "FOLLOW_UP_SCHEDULED":
    case "FOLLOW_UP_SENT":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Not Called" };
    case "CALL_QUEUED":
    case "IN_CALL":
    case "CALL_SCHEDULED":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Scheduled" };
    case "CALL_COMPLETED":
      return { linkedInStage: "Follow Up Msg", emailStage: "Email Sent", callStage: "Answered" };
    case "CONVERSATION_ACTIVE":
    case "REPLIED":
      return { linkedInStage: "Responded", emailStage: "Responded", callStage: "Responded" };
    case "CLOSED":
      return { linkedInStage: "Responded", emailStage: "Responded", callStage: "Responded" };
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
          const stages = mapBackendStateToFrontend(p.current_state);
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
