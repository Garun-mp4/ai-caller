# AI Call Agent MVP

Local-first SaaS-style MVP for managing phone leads, campaigns, callbacks and AI-assisted calls. The default configuration is deliberately **mock-first**: it runs without Twilio, Codex, Vosk or Piper so the complete CRM/campaign/scheduler flow can be tested locally before paid telephony and voice models are connected.

## What is included

- FastAPI + SQLAlchemy 2 + Alembic + SQLite backend.
- Next.js + TypeScript + React + Tailwind dashboard.
- Local admin authentication (`AUTH_MODE=local`). A `chatgpt` mode/config boundary exists, but no unofficial OpenAI OAuth flow is implemented.
- TXT lead import with phone normalization, validation, duplicate detection and file size limits.
- CRM lead statuses including irreversible-by-scheduler `DO_NOT_CALL` safeguard.
- Campaigns with compliance confirmation timestamp, Start/Pause/Stop and lead attachment.
- Lightweight asyncio scheduler (default one concurrent call), callback scheduling and allowed calling hours.
- Call history, transcripts, summaries and latency fields.
- Mock LLM and mock telephony for free local E2E development.
- Codex CLI provider isolated behind `LLMProvider`, executed asynchronously with `shell=False` and a timeout.
- Vosk provider with the model cached process-wide and loaded only once on first use.
- Piper provider isolated behind `TTSProvider`.
- Twilio outbound call provider plus Media Streams WebSocket, µ-law/PCM conversion, simple VAD and barge-in (`clear` on detected speech).
- `HotLeadCreated` persisted event seam for a future Telegram notification handler. Telegram itself is intentionally not implemented.

## Architecture

`frontend` talks to the FastAPI JSON API. Business data is stored through SQLAlchemy, so PostgreSQL can later replace SQLite by changing `DATABASE_URL`. The scheduler depends on provider/service interfaces rather than on Twilio, Codex or Telegram directly.

Live audio path:

`Twilio Media Stream -> audio codec/resampler/VAD -> Vosk -> LLMProvider -> structured decision -> Piper -> µ-law -> Twilio`

The live WebSocket is intentionally thin: audio, STT, LLM and TTS are separate modules. Mock mode exercises the CRM/campaign lifecycle without requiring audio binaries or external accounts.

## Requirements

- Python 3.12+ (3.13 also works with the included code/dependencies)
- Node.js 20+ (22 recommended)
- npm
- Optional for live mode: Codex CLI, Piper, a Russian Vosk model, Twilio account/number

## Installation

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\dev.ps1
```

### Linux/macOS

```bash
chmod +x scripts/*.sh
./scripts/setup.sh
./scripts/dev.sh
```

Open:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs

Default development login is `admin` / `admin`. Change `LOCAL_ADMIN_USERNAME`, `LOCAL_ADMIN_PASSWORD` and `JWT_SECRET` in `.env` for any non-throwaway environment.

## Quick mock-mode test

`.env.example` defaults to:

```env
LLM_PROVIDER=mock
TELEPHONY_PROVIDER=mock
AUTH_MODE=local
```

1. Sign in.
2. Open **Leads** and import a TXT file, e.g. one E.164 number per line.
3. Open **Campaigns**, create a campaign and click Start. Starting records the compliance confirmation.
4. Click **Run one scheduler tick** to immediately process a queued lead even if you are outside calling hours. The background scheduler itself respects configured calling hours.
5. Inspect Calls, Lead Details and Callbacks.

Mock call outcomes are deterministic from the last phone digit so interested, callback and do-not-call paths are easy to test.

## TXT format

Required format:

```text
+79991111111
+79992222222
```

Also accepted:

```text
ООО Альфа,+79991111111
ООО Бета | +79992222222
```

The importer trims whitespace, normalizes possible phone numbers to E.164, rejects invalid lines and removes both in-file and database duplicates.

## Vosk setup

The package is installed with backend dependencies, but the speech model is **not** downloaded automatically. Download a current lightweight Russian Vosk model from the official Vosk models page, unpack it locally and set:

```env
STT_PROVIDER=vosk
VOSK_MODEL_PATH=/absolute/path/to/vosk-model-small-ru
```

You can also place it under `models/vosk/model`. `VoskProvider` caches a single `Model` object for the process; it is not reloaded for every utterance.

## Piper setup

Install the Piper CLI/binary for your OS and download a Russian ONNX voice with its JSON config. Set:

```env
PIPER_BINARY=piper
PIPER_MODEL_PATH=/absolute/path/to/ru_voice.onnx
PIPER_CONFIG_PATH=/absolute/path/to/ru_voice.onnx.json
```

The preferred `piper-tts` Python path loads `PiperVoice` once per backend process and reuses it for every utterance. A safe `shell=False` Piper CLI fallback is retained for compatibility, but the in-process provider is recommended for low latency. In mock telephony mode Piper is not needed.

## Codex CLI setup/login

Install the **official Codex CLI**, ensure `codex` is available on `PATH`, and use its official login flow. Then set:

```env
LLM_PROVIDER=codex
CODEX_BINARY=codex
CODEX_MODEL=
CODEX_REASONING_EFFORT=low
```

The provider checks that the binary is present and exposes its CLI health/version in Settings. No ChatGPT browser cookies/tokens are read or copied.

### Website auth vs Codex auth

These are separate mechanisms:

- `AUTH_MODE=local` controls who can open this local web app.
- Codex CLI maintains its own official CLI login/credentials.

When OpenAI has issued a website OAuth client for your app, set `AUTH_MODE=chatgpt`, `OPENAI_OAUTH_CLIENT_ID`, optional `OPENAI_OAUTH_CLIENT_SECRET` (depending on your registered token-endpoint auth method), and `OPENAI_OAUTH_REDIRECT_URI`. The backend uses the official Authorization Code + PKCE/OpenID Connect endpoints, validates issuer/audience/nonce and then creates its own local app session. If you do not have an issued website client, keep `AUTH_MODE=local`. The app never transforms website OAuth credentials into Codex CLI credentials.

## Twilio setup

Set:

```env
TELEPHONY_PROVIDER=twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+...
PUBLIC_BASE_URL=https://your-public-https-host
```

Twilio must reach your FastAPI server over public HTTPS/WSS. For local development use a secure tunnel of your choice and point `PUBLIC_BASE_URL` at it. The outbound call fetches `/api/telephony/twiml/{call_id}`, which connects a bidirectional Media Stream to `/api/telephony/media/{call_id}`.

The media layer decodes Twilio µ-law/8 kHz, resamples to 16 kHz for Vosk, detects speech using a low-cost energy VAD, and sends `clear` when client speech arrives while TTS is playing (barge-in). Piper output is converted back to 8 kHz µ-law.

> Real telephone behavior depends on your Twilio account/region/number capabilities and tunnel/network latency. Validate consent, calling rules, recording/transcription requirements, local time windows and any required disclosures for the jurisdictions you operate in.

## Settings

The Settings page exposes non-secret model/provider configuration plus editable agent/call preferences. Secret values such as Twilio tokens are never sent to the frontend. Model/provider path changes are persisted and take effect after a backend restart because Vosk/Piper/LLM providers are intentionally process-cached; calling-hour/attempt settings are read dynamically.

## Tests

From the repository root after setup:

```bash
source .venv/bin/activate          # Linux/macOS
cd backend
pytest -q
alembic upgrade head
```

Windows:

```powershell
cd backend
..\.venv\Scripts\pytest.exe -q
..\.venv\Scripts\alembic.exe upgrade head
```

Frontend production build:

```bash
cd frontend
npm run build
```

Tests cover TXT import, duplicate detection, phone validation, structured agent output, mock LLM, mock telephony, campaign compliance, scheduler/callback flow and DO_NOT_CALL exclusion.

## Production considerations

This is an MVP, not a production dialer. Before production use, migrate to PostgreSQL, use a real job queue/worker, add robust distributed call locks/idempotency, signed Twilio webhook validation, rate limiting, TLS, secrets management, per-user authorization, audit logs, proper WebRTC/telephony observability, a production-grade VAD, explicit timezone handling for natural-language callback dates, retries/dead letters, and a legal/compliance review appropriate to your target markets.

## Replacing Codex CLI with OpenAI API later

Implement another `LLMProvider` (for example `OpenAIProvider`) with the same `generate(system_prompt, history, user_text)` contract, select it in `llm/factory.py`, and expose `LLM_PROVIDER=openai`. CRM, scheduler, agent parsing and telephony code do not need to change.

## Future Telegram module

The core emits/persists a `HotLeadCreated` event. A future independent `TelegramNotificationHandler` can consume that event and send company, phone and summary. No scheduler/CRM code needs to import Telegram SDKs.

## Troubleshooting

- **Frontend says unauthorized**: sign in again; check backend is on port 8000 and `NEXT_PUBLIC_API_URL`.
- **Codex health fails**: run `codex --version`, then complete the official CLI login; keep `LLM_PROVIDER=mock` until ready.
- **Vosk unavailable**: verify `VOSK_MODEL_PATH` points to an unpacked model directory.
- **Piper unavailable**: verify both binary and ONNX paths. Mock telephony does not require it.
- **Twilio call fails immediately**: confirm credentials/number, public HTTPS URL, and that Twilio can reach `/api/telephony/twiml/{id}`.
- **Callbacks not firing**: background scheduler respects `CALLING_HOURS_START/END`; use the manual scheduler tick only for local testing.
