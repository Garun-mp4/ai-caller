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
- Vosk provider caches its loaded model per provider instance and path.
- Piper provider isolated behind `TTSProvider`.
- Twilio outbound call provider plus Media Streams WebSocket, µ-law/PCM conversion, simple VAD and barge-in (`clear` on detected speech).
- `HotLeadCreated` persisted event seam for a future Telegram notification handler. Telegram itself is intentionally not implemented.

## Architecture

`frontend` talks to the FastAPI JSON API. Business data is stored through SQLAlchemy, so PostgreSQL can later replace SQLite by changing `DATABASE_URL`. The scheduler depends on provider/service interfaces rather than on Twilio, Codex or Telegram directly.

Live audio path:

`Twilio Media Stream -> audio codec/resampler/VAD -> Vosk -> LLMProvider -> structured decision -> Piper -> µ-law -> Twilio`

The live WebSocket is intentionally thin: audio, STT, LLM and TTS are separate modules. Mock mode exercises the CRM/campaign lifecycle without requiring audio binaries or external accounts.

## API contracts

`GET /api/leads` returns a page object with `items`, `total`, `page`, `page_size` and `page_count`. It supports `status`, `campaign`, `search`, `page`, `page_size` (1–100), `sort_by` and `sort_order`; search covers contact name, company and phone. Campaigns can preview the number of eligible contacts at `GET /api/campaigns/{id}/audience`; attachment only includes `NEW`, `QUEUED` and `CALLBACK` leads, so completed and `DO_NOT_CALL` contacts stay out of the queue.

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

Default development login is `admin` / `admin`. Change `LOCAL_ADMIN_USERNAME`, `LOCAL_ADMIN_PASSWORD` and `JWT_SECRET` in `.env` for any non-throwaway environment. Production startup rejects the built-in defaults, local passwords shorter than 12 characters, and JWT keys shorter than 32 characters.

### Docker Compose

Copy `.env.example` to `.env` if you do not already have a local configuration, then run:

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

The frontend is at http://localhost:3000 and the API at http://localhost:8000. Compose builds dependencies into images instead of reinstalling them on every restart, waits for the API database readiness check before starting the frontend, and binds both ports to loopback by default. SQLite remains at `backend/ai_caller.db`; keep the `./backend:/app/backend` bind mount when changing the Compose setup. Set `HOST_BIND_ADDRESS` explicitly if the service must be reachable from another machine. Do not use `docker compose down -v` when retaining the frontend dependency/cache volumes matters.

## Quick mock-mode test

`.env.example` defaults to:

```env
LLM_PROVIDER=mock
TELEPHONY_PROVIDER=mock
AUTH_MODE=local
```

1. Sign in.
2. Open **Leads** and import a TXT file, e.g. one E.164 number per line.
3. Open **Campaigns**, create a campaign, review its eligible audience and confirm contact authorization before starting.
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

## Audio and speech-model checks

The backend suite covers PCM16/µ-law conversion, resampling, voice activity detection, bounded speech buffering, Twilio media-stream turns, barge-in, and Piper CLI cleanup. Two short Russian recordings from Google’s [FLEURS-R development split](https://huggingface.co/datasets/google/fleurs-r) are included under `backend/tests/assets/fleurs-ru-dev`; they are attributed and licensed CC BY 4.0 in that directory's README.

For actual inference checks, place the optional model files at the paths below. The Vosk catalog lists `vosk-model-small-ru-0.22` at about 45 MB under Apache 2.0. The Piper `ru_RU-dmitri-medium` voice is about 63 MB; its [model card](https://huggingface.co/rhasspy/piper-voices/blob/v1.0.0/ru/ru_RU/dmitri/medium/MODEL_CARD) identifies its training dataset as CC0, and the pinned model files are from the `v1.0.0` voice release. These weights are ignored by Git and are not included in the repository.

- Download the [Russian Vosk small model](https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip), unpack it to `models/vosk/model`.
- Download the [Piper ONNX voice](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx) and [matching JSON config](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx.json), then save them as `models/piper/voice.onnx` and `models/piper/voice.onnx.json`.
- Run `docker compose exec -T backend pytest -m model_integration -q` for warm-up, health, FLEURS-R transcription, Piper synthesis, and Piper-to-Vosk recognition checks.

The full backend test run also executes these model checks when model files are present and skips only the model-dependent cases when they are absent. Model inference requires additional memory and takes longer than the unit suite.

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

The Settings page exposes non-secret model/provider configuration plus editable agent/call preferences. Secret values such as Twilio tokens are never sent to the frontend. Provider, model and model-path changes clear the relevant cached provider; new calls use the updated settings immediately. Loaded speech models remain attached to the in-flight provider instance until active work releases it. Calling-hour and attempt settings are read dynamically, and invalid legacy values are displayed using their safe effective values.

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
npm run lint
npm run typecheck
npm test
npm run build
```

The frontend browser suite runs against a local Next.js server and mocks the API, so it does not make real calls or require provider credentials. Install its browser once with `npx playwright install chromium`.

Tests cover TXT import, duplicate detection, phone validation, paginated and sorted lead queries, settings validation and secret filtering, campaign audience eligibility, duplicate scheduler ticks, stale call reservations, Twilio callback idempotency, structured agent output, mock providers and DO_NOT_CALL exclusion.

## Production considerations

This is an MVP, not a production dialer. Production mode currently rejects known development credentials, and Twilio HTTP/WebSocket callbacks validate signatures. Before production use, migrate to PostgreSQL, use a real job queue/worker, add robust distributed call locks/idempotency, rate limiting, managed secrets, per-user authorization, audit logs, stronger telephony observability, a production-grade VAD, explicit timezone handling for natural-language callback dates, retries/dead letters, and a legal/compliance review appropriate to your target markets.

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
