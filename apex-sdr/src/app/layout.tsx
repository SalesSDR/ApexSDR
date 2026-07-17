import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Apex SDR — AI-Powered Sales Development Platform",
  description:
    "Apex SDR is an enterprise-grade AI SDR platform that automates outbound prospecting, ICP definition, and multi-channel engagement.",
  keywords: ["SDR", "AI Sales", "Outbound", "Prospecting", "B2B"],
  openGraph: {
    title: "Apex SDR",
    description: "AI-Powered Sales Development Platform",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} antialiased`}>
        <div className="flex h-screen overflow-hidden" style={{ background: "var(--apex-bg)" }}>
          <Sidebar />
          <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
