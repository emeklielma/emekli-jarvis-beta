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

## Notes

- Windows-only in several places: `os.startfile`, MCI audio playback, PowerShell-based tools, `winmm`.
- No test suite beyond `test_models.py` (a manual diagnostic script, not an automated test).
