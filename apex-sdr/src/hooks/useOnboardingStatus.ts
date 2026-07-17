"use client";

import { useState, useEffect } from "react";
import type { OnboardingStatus } from "@/types";
import onboardingData from "@/mocks/onboarding.json";

interface UseOnboardingStatusReturn {
  data: OnboardingStatus | null;
  loading: boolean;
  error: string | null;
}

export function useOnboardingStatus(): UseOnboardingStatusReturn {
  const [data, setData] = useState<OnboardingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTimeout(() => {
      try {
        setData(onboardingData as OnboardingStatus);
      } catch {
        setError("Failed to load onboarding status");
      } finally {
        setLoading(false);
      }
    }, 300);
  }, []);

  return { data, loading, error };
}
