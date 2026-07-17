# ApexSDR

ApexSDR is an autonomous AI-driven Sales Development Representative (SDR) pipeline. It combines a modern Next.js frontend with a robust, event-driven Python backend to orchestrate personalized outreach across multiple channels (LinkedIn, Email, and Voice) autonomously.

## 🚀 What's Working Right Now

The core infrastructure and the critical autonomous workflows are fully operational:

1. **Conversational ICP Builder (AI-Powered Filter Extraction)**
   - **Status:** Fully Working (with robust fallback)
   - The UI allows you to type natural language (e.g., *"Find me VPs of Engineering at Series B Fintechs in New York using AWS"*). 
   - A dedicated FastAPI endpoint (`/api/v1/icp/parse`) securely passes this to **Gemini 2.0 Flash**, which intelligently parses the unstructured text into a highly structured JSON filter schema.
   - Includes an intelligent Regex Fallback mechanism that gracefully intercepts and extracts parameters if the LLM API hits a rate limit (429 Quota Exceeded).

2. **Autonomous Background State Machine (ARQ + Redis)**
   - **Status:** Fully Working
   - Instead of a human clicking "Advance", an asynchronous supervisor cron task (`autonomous_pipeline_supervisor_task`) sweeps the Postgres database every 5 minutes.
   - It identifies any prospects whose cooldown timers have expired (e.g., `INITIAL_MSG_SENT` -> `PENDING_FOLLOW_UP`) and automatically dispatches background worker tasks to execute the next sequence action.

3. **Inbound Reply Detection & Intent Parsing**
   - **Status:** Fully Working (Webhooks)
   - The backend listens to Unipile webhooks at `/api/v1/webhooks/unipile`.
   - When a prospect replies on LinkedIn or Email, the webhook catches the message, matches it to the prospect ID, and uses the AI to classify the prospect's intent (e.g., `POSITIVE_REPLY`, `NOT_INTERESTED`).
   - If the prospect is interested, it halts the automated sequence and flags them for a human handoff.

4. **Resilient AI Generation (With Fallbacks)**
   - **Status:** Fully Working
   - The system utilizes `gemini-2.0-flash` to dynamically generate highly contextual LinkedIn messages, Cold Emails, and follow-ups.
   - If the LLM goes down or hits limits, the pipeline instantly falls back to dynamically injected local text templates, ensuring outreach *never* halts due to third-party API outages.

5. **Prospect Enrichment Engine**
   - **Status:** Partially Working (API Tier Limit)
   - The system is wired up to Apollo.io (`/api/v1/people/match`) to enrich prospects. However, Apollo's free tier explicitly denies access to the `/match` endpoint. The pipeline currently gracefully catches this `403` error and allows manual overrides.

## 🏗️ Architecture

The application is built on a scalable, decoupled monorepo structure.

### 1. Frontend (`/apex-sdr`)
- **Framework:** Next.js (App Router), React, TypeScript.
- **Styling:** Custom CSS with Framer Motion for premium micro-interactions.
- **Role:** Provides the dashboard, active queue views, and the conversational ICP builder.

### 2. Backend (`/backend`)
- **API Gateway:** FastAPI (Python) handles all incoming REST traffic, webhooks, and frontend requests asynchronously.
- **Task Queue:** ARQ (Async Redis Queue) orchestrates background jobs, rate-limiting, and cron supervisors.
- **Database:** PostgreSQL (AsyncPG) for durable, relational state management of prospects and sequences.
- **Cache / Broker:** Redis handles job state and fast KV lookups.
- **Integrations Layer:** Modular integration wrappers in `src/app/services/` for:
  - **Gemini:** Contextual AI generation & parsing.
  - **Unipile:** LinkedIn & Email orchestration.
  - **Apollo:** B2B contact enrichment.
  - **Twilio:** Telephony & voice logging.

## ⚙️ How to Run Locally

### 1. Start the Backend Infrastructure
The entire backend is orchestrated via Docker Compose. Ensure Docker is running.
```bash
cd backend
docker-compose up -d --build
```
This spins up:
- Postgres on port `5433`
- Redis on port `6380`
- FastAPI Server on port `8000`
- ARQ Background Worker

### 2. Start the Frontend UI
```bash
cd apex-sdr
npm install
npm run dev
```
Navigate to `http://localhost:3000` to interact with the dashboard.
