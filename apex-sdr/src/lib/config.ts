/**
 * Centralized production / dev config.
 *
 * All values are read from Next.js public environment variables at BUILD TIME
 * (NEXT_PUBLIC_* prefix). Fallbacks ensure localhost dev never breaks even if
 * .env.local is missing a variable.
 *
 * To configure for production, set these in apex-sdr/.env.production:
 *   NEXT_PUBLIC_APP_URL          — live app entry point (e.g. https://app.apex-sdr.com)
 *   NEXT_PUBLIC_API_URL          — FastAPI backend base URL
 *   NEXT_PUBLIC_CHAT_WEBHOOK_URL — chat message endpoint
 *   NEXT_PUBLIC_SITE_URL         — Hostinger marketing domain
 */

export const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export const CHAT_WEBHOOK_URL =
  process.env.NEXT_PUBLIC_CHAT_WEBHOOK_URL ||
  `${API_BASE_URL}/chat/message`;

export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
