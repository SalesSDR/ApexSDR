import { Metadata } from "next";
import { Hero } from "@/components/marketing/Hero";
import { FeatureShowcase } from "@/components/marketing/FeatureShowcase";

export const metadata: Metadata = {
  title: "Apex SDR | Autonomous AI Growth & Sales Platform",
};

export default function MarketingHomePage() {
  return (
    <>
      <Hero />
      <FeatureShowcase />
    </>
  );
}
