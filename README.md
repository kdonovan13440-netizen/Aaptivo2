# Aptivo Agent

A modular personal-assistant foundation for voice calls, calendar workflows, task management, file operations, and explicitly authorized device actions.

## Current scope
- FastAPI API with health, task, assistant, call-webhook, and action-queue endpoints.
- Groq chat-completions adapter (API key supplied through environment).
- Provider-neutral telephony and calendar interfaces with safe, unconfigured defaults.
- Task persistence in SQLite by default.
- File operations are restricted to a configured workspace directory.
- Device actions are queued for a future trusted local companion; the server does **not** silently control a phone or computer.

## Vertical markets
One deployment can work in one market at a time. Set `AGENT_VERTICAL` in the
environment to pick it, plus `BUSINESS_NAME` (and optionally `BUSINESS_HOURS`)
to personalize it, then restart. The phone greeting, the services the agent
talks about, the questions it asks to book, and its rules all follow the market:

- `personal` — a personal assistant (the default).
- `home_services` — HVAC, plumbing and handyman companies.
- `auto_repair` — auto repair shops.
- `salon_barber` — salons and barbershops.
- `dental` — dental office front desk (never gives medical advice).
- `real_estate` — agents and teams (never quotes prices or values).
- `restaurant` — reservations and takeout (takes requests, never guarantees a table).
- `resale` — Marketplace and Craigslist sellers (takes offers, never accepts or declines them).

`GET /v1/verticals` lists every market and which one is active. The dashboard
shows the same. Every market follows the same honesty rules: collect the
details a human needs, read them back, and present bookings as requests until
the business or a connected calendar confirms them.

## Run locally
1. Copy `.env.example` to `.env` and set a long random `API_KEY`.
2. Add `GROQ_API_KEY` to enable AI responses.
3. Install: `python -m venv .venv && pip install -r requirements.txt`
4. Start: `uvicorn app.main:app --reload`
5. Open `/docs` for the API.

Send `X-API-Key: <your API_KEY>` on protected API routes.

## Integrations to configure
- **Groq:** `GROQ_API_KEY`, `GROQ_MODEL`. The prompt-guard model is for safety classification, not the primary conversational model.
- **Telephony:** configure a provider such as Twilio and a public HTTPS webhook URL. This starter does not place real calls until a provider adapter is implemented and credentials are configured.
- **Calendars:** implement OAuth consent and provider adapters (Google Calendar / Microsoft Graph). No calendar is accessed by default.
- **Phone/computer control:** install a separately authenticated local companion and request user confirmation for consequential actions. A hosted API cannot directly operate a personal device.

## Safety
Never commit `.env`, tokens, call recordings, transcripts, or customer data. Obtain required consent for calls and recordings; respect opt-outs, do-not-call rules, and local calling-hour laws. Require explicit confirmation before sending messages, deleting files, booking appointments, or taking device actions.

This is a starter foundation, not a production-ready live calling or remote-control service.
