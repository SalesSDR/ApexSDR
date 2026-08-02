/**
 * Centralized production / dev config for the public marketing site.
 *
 * Sprint 7.1: this used to also define its own API_BASE_URL, duplicating
 * (and drifting from) lib/api.ts's - and every dashboard page that read
 * API_BASE_URL from here was calling the backend with plain `fetch()`,
 * never attaching the Authorization header lib/api.ts's fetchApi() adds.
 * There is now exactly one API_BASE_URL (lib/api.ts); anything that needs
 * to call the authenticated backend should import fetchApi from there
 * instead of building its own fetch() calls against a base URL.
 *
 * To configure for production, set these in apex-sdr/.env.production:
 *   NEXT_PUBLIC_APP_URL          — live app entry point (e.g. https://app.apex-sdr.com)
 *   NEXT_PUBLIC_CHAT_WEBHOOK_URL — chat message endpoint
 *   NEXT_PUBLIC_SITE_URL         — Hostinger marketing domain
 */
import { API_BASE_URL } from "@/lib/api";

export const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL || "https://apex-sdr-i9xg.vercel.app";

export const CHAT_WEBHOOK_URL =
  process.env.NEXT_PUBLIC_CHAT_WEBHOOK_URL ||
  `${API_BASE_URL}/chat/message`;

export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
