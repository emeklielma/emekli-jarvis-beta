# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Jarvis is a voice-controlled desktop AI assistant (Iron Man-style). Python backend does speech recognition, TTS, and tool execution; a React frontend renders the UI, shown either in a browser or inside a native window via `pywebview`/Electron.

There are two independent ways to run the assistant:
- **CLI mode** (`main.py`) — fully console-based loop, no UI.
- **App mode** (`server.py` + `frontend/`) — FastAPI backend pushes state over a WebSocket to the React UI, which is displayed via `jarvis_app.py` (pywebview window pointed at the Vite dev server) or Electron (`frontend/electron.cjs`).

Both modes share the same `ai_module.py` (Gemini brain) and `tools.py` (function-calling tools) and `speech_module.py` (STT/TTS).

## Running

Backend (Python), from repo root:
```
pip install -r requirements.txt
python main.py          # CLI voice/text loop
python server.py         # FastAPI server on :8000, WebSocket at /ws, POST /api/chat
python jarvis_app.py     # native window wrapping the running Vite dev server (expects it on :5173)
```

Frontend, from `frontend/`:
```
npm install
npm run dev       # Vite dev server on :5173
npm run build     # production build
npm run lint      # oxlint
npm run electron  # run Electron shell (electron.cjs) instead of pywebview
```

Requires a `.env` file in repo root with `GEMINI_API_KEY=...` (see `ai_module.py`, `test_models.py`). `test_models.py` is a standalone script to list what Gemini models the configured key can access — useful when the model list in `ai_module.py` needs updating.

## Architecture

**AI brain (`ai_module.py`)**: talks to the Gemini API directly over raw HTTP (deliberately bypasses the `google-generativeai` SDK — see the comment about `ACCESS_TOKEN_TYPE_UNSUPPORTED`). Maintains `conversation_history` as module-level global state (in-memory, not persisted, shared across all callers within a process). `generate_response(prompt)` is the single entry point used by both `main.py` and `server.py`.

- Cycles through a hardcoded `MODELS` list on HTTP 429, wrapping around when all are exhausted.
- Has a local 5-second rate limiter across all calls.
- Function calling: if Gemini returns a `functionCall`, the tool is looked up in `tools.TOOL_MAP`, executed, and the result is fed back in a second request to get the final spoken response.

**Tools (`tools.py`)**: plain Python functions (open a website, search YouTube, launch a Windows app, run a PowerShell command, fetch news RSS, simulate key presses/typing via `pyautogui`). Two parallel structures must stay in sync when adding a tool:
1. `TOOL_MAP` — name → callable.
2. `GEMINI_TOOLS` — the JSON function-declaration schema sent to Gemini.

`run_terminal_command` executes arbitrary PowerShell from model output — treat any change here as security-sensitive.

**Speech (`speech_module.py`)**: `speak()` uses `edge_tts` to synthesize audio and plays it via Windows MCI (`ctypes.windll.winmm`) — Windows-only. `listen()`/`record_audio()` self-calibrate a silence threshold from a half-second of ambient noise, then stream mic input in 0.25s chunks via `sounddevice`, auto-stopping after ~0.75s of silence; transcription goes through `speech_recognition`'s Google recognizer.

**Server mode (`server.py`)**: runs a background daemon thread (`audio_listener_loop`) that continuously listens via `speech_module`, calls `ai_module.generate_response`, synthesizes a reply with `edge_tts` to `frontend/public/response.mp3`, and enqueues UI events onto a thread-safe `queue.Queue`. A separate asyncio task (`broadcast_worker`) drains that queue and pushes JSON messages to connected WebSocket clients — this bridge exists because the listener thread isn't part of the asyncio event loop. The UI can toggle the mic or interrupt in-flight listening/thinking via `{"action": "toggle_mic"|"interrupt"}` WebSocket messages, backed by the globals `MIC_ACTIVE`/`INTERRUPT_FLAG`.

**Frontend (`frontend/src/App.jsx`)**: connects to the `/ws` WebSocket for live status/log updates and plays `audioUrl` responses as they arrive; also can POST plain text to `/api/chat` for typed input.

**Phone access**: Vite listens on all interfaces (`server.host: true`) and proxies `/ws` and `/api` to the Python server on :8000, so the frontend always connects to its own origin — never hardcode `localhost:8000` in the UI. `npm run dev:phone` serves the same UI over HTTPS on :5174 (self-signed, `@vitejs/plugin-basic-ssl`) because phone browsers only allow the microphone (Web Speech API, "BU CİHAZIN MİKROFONU" button) on HTTPS. The server keeps the recent chat in `chat_history` (in `server.py`) and sends it as a `{"type": "history"}` message on every new WebSocket connection, so all devices show the same conversation.

**Claude launcher**: `core/intents.py` matches Turkish/English phrases like "uygulama yapacağım" or "<isim> projesine devam edelim" before the LLM is called (`process_user_input` in `server.py`) and runs `core/claude_launcher.open_claude`, which opens Claude Code (`claude` / `claude --continue`) in the matching project folder, falling back to the Claude desktop app, then claude.ai. The same function is exposed to Gemini as the `open_claude` tool (`tools/claude_tools.py`).

**Phone calls (`core/telephony.py`)**: normal phone calls through Twilio. Jarvis can call only the owner's number (`call_owner()` / the `call_my_phone` tool take no number argument, and "beni ara" is a fast-path intent), and only the owner may call Jarvis. Twilio webhooks hit `/phone/voice` → optional DTMF PIN (`/phone/pin`) → a `<Gather input="speech">` loop through `/phone/speech`, which answers via `ai_module.generate_text(..., allow_tools=False, extra_instruction=PHONE_INSTRUCTION)`. Every request is checked against `X-Twilio-Signature` (rebuilt from `JARVIS_PUBLIC_URL`, since the local server only sees the tunnel) and the owner's number. The server is reachable from the internet through an ngrok tunnel, so `PublicTunnelGuard` in `server.py` blocks everything except `/phone/*` on the public host. Keep it that way, because `/ws` can run tools on the PC. Phone tools stay off unless `JARVIS_PHONE_TOOLS=1` and a PIN are both set, because caller ID can be spoofed. At startup, `sync_incoming_webhook` points the Twilio number at `JARVIS_PUBLIC_URL/phone/voice`. See `.env.example` for the settings.

**Linphone calls (`core/sip_phone.py`)**: this is the free alternative to Twilio. It is a small self-contained SIP user agent over UDP. It registers Jarvis' own sip.linphone.org account and answers 401/407 digest challenges (MD5 or SHA-256). Media is RTP with G.711 PCMU/PCMA; the codec tables are its own because `audioop` was removed in Python 3.13, and there is no ICE or STUN. Jarvis calls only `JARVIS_SIP_OWNER` and accepts INVITEs only from that account and only when they arrive from the SIP server's address. `SipCall` runs VAD on the incoming audio, then Google STT (8 kHz), `respond` (`ai_module.generate_text` with tools off), and edge-tts decoded and resampled to 8 kHz. `server.start_sip_phone()` sets `sip_phone.instance`, and `telephony.call_owner_any()` prefers it over Twilio. pyVoIP was rejected because it can't answer 407 on INVITE and it depends on `audioop`.

**Standalone phone (`jarvis_telefon.py` + `Jarvis-Telefon.bat`)**: this runs the Linphone line next to any Jarvis folder without touching its code. It needs `core/sip_phone.py` copied next to it as `sip_phone.py`, so `sip_phone.py` must stay free of other `core` imports. It talks to Gemini over the OpenAI-compatible endpoint, or to Ollama (`LLM_PROVIDER`/`OLLAMA_*` in `.env`) using stdlib `urllib`. It accepts `POST http://127.0.0.1:8431/call` from other programs, and typing `ara` in its window starts a call.

**Environment variables** (all optional, in `.env`): `JARVIS_STT_LANG` (speech recognition language, default `tr-TR`), `JARVIS_MIC_DEVICE` (input device index or name substring), `JARVIS_TTS_VOICE` (force one edge-tts voice; default picks Turkish or English per sentence), `JARVIS_PROJECTS_DIRS` (`;`-separated folders searched for projects), `JARVIS_NEW_PROJECTS_DIR`, `JARVIS_CLAUDE_MODE` (`auto`|`code`|`desktop`|`web`), `JARVIS_SIP_USER`/`JARVIS_SIP_PASSWORD`/`JARVIS_SIP_OWNER` (+ optional `JARVIS_SIP_DOMAIN`, `JARVIS_SIP_PROXY`, `JARVIS_SIP_PORT`, default 5070), `JARVIS_WAKE_WORD=0` (disable the openwakeword/clap listener, which keeps a second mic stream open).

**Mic troubleshooting**: `python mic_test.py [device]` lists input devices, measures noise vs. speech level against the same threshold `speech_module` uses, and tries Google STT. `launch.py` writes backend output to `jarvis_server.log`.

## Notes

- Windows-only in several places: `os.startfile`, MCI audio playback, PowerShell-based tools, `winmm`.
- No test suite beyond `test_models.py` (a manual diagnostic script, not an automated test).
