# ApexSDR Technical Architecture

## Core Philosophy
ApexSDR is designed around an asynchronous, event-driven architecture using **FastAPI** as the API layer, **PostgreSQL** for state persistence, and **Redis / ARQ** for background queue processing.

## Components

### 1. API Gateway (FastAPI)
Exposes REST endpoints for the dashboard UI, Webhooks (Twilio/Email), and external CRM syncing. All logic here is purely CRUD or lightweight intent-parsing; heavy processing is deferred to the queue.

### 2. Decision Engine (The Brain)
An isolated module (`src/app/services/decision/engine.py`) that observes a `Prospect`'s state, reviews active `ConversationMemory`, and determines the next best action (`WAIT`, `SEND_EMAIL`, `BOOK_MEETING`).

### 3. Compliance Engine (The Shield)
Acts as a middleware filter between the Decision Engine and external execution adapters. Before any action (email, call, message) is enqueued, it checks Do Not Contact lists, unsubscriptions, GDPR rules, and rate limits. If blocked, it logs a `ComplianceLog` and updates the `ActivityTimeline`.

### 4. Background Workers (ARQ)
Embedded inside the FastAPI startup lifecycle to simplify deployment, ARQ pulls jobs from Redis. Tasks include:
- Executing outbound sequences.
- Enriching prospect profiles via waterfall APIs.
- Summarizing AI voice calls.
- Processing CRM/Calendar syncs.

### 5. AI Integrations
- **Generative Text**: Google Gemini (`google.generativeai`) is used extensively via Adapter Patterns to generate outbound emails, craft LinkedIn messages, parse raw buying signals into intents, and orchestrate Voice conversations in real-time.
