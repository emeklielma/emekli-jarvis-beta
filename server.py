import os
import asyncio
import threading
import subprocess
import time
import json
import psutil
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import core modules
from core import ai_module as am
from core import speech_module as sm
from core.state import state

# Preload tools (they auto-register themselves to tools.registry)
import tools.system_tools
import tools.browser_tools
import tools.vision_tools
import tools.memory_tools
import tools.system_diagnostics
import tools.integration_tools
import tools.smart_home_tools
import tools.gui_tools
import tools.advanced_system_tools
import tools.productivity_tools
import tools.claude_tools
import tools.phone_tools
from core import telephony
from core import intents
from core import claude_launcher
from core.tray import tray_manager

try:
    from core import wake_word
except Exception as e:
    # openwakeword eksik/bozuk olsa bile sunucu ve mikrofon çalışmaya devam etsin
    print(f"[WAKE WORD] Disabled: {e}")
    wake_word = None

app = FastAPI()


class PublicTunnelGuard:
    """Twilio'nun ulaşabilmesi için sunucu ngrok ile internete açılıyor. O adresten gelen
    isteklerde SADECE /phone/ yollarına izin ver; /ws ve /api bilgisayarda komut
    çalıştırabildiği için internete kapalı kalmalı."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            host = telephony.public_host()
            headers = {k.decode("latin-1").lower(): v.decode("latin-1").lower() for k, v in scope.get("headers", [])}
            via_tunnel = bool(host) and host in (headers.get("host", ""), headers.get("x-forwarded-host", ""))
            if via_tunnel and not scope["path"].startswith("/phone/"):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    await Response("Forbidden", status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)


app.add_middleware(PublicTunnelGuard)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WS BROADCAST ERROR] {e}")

manager = ConnectionManager()
main_loop = None

# Son sohbet kayıtları: telefondan / başka bir pencereden bağlanan istemciler
# bağlanır bağlanmaz aynı geçmişi görsün diye sunucuda tutuluyor.
chat_history = deque(maxlen=150)

async def log_message(sender: str, text: str):
    entry = {"sender": sender, "text": text}
    chat_history.append(entry)
    await manager.broadcast({"type": "log", **entry})

def safe_broadcast(message):
    """Safely broadcasts a message from background threads."""
    global main_loop
    if main_loop is None or not main_loop.is_running():
        return
    try:
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), main_loop)
    except Exception as e:
        print(f"[SAFE BROADCAST ERROR] {e}")

async def process_user_input(text: str):
    """Processes user text through the LLM stream, sends tokens to UI, and buffers for TTS."""
    await log_message("user", f"USR: {text}")
    await manager.broadcast({"type": "status", "value": "THINKING"})

    # "uygulama yapacağım" / "<isim> projesine devam edelim" -> doğrudan Claude'u aç (LLM'e gerek yok)
    claude_intent = intents.match_claude_intent(text)
    if claude_intent:
        await run_claude_intent(claude_intent)
        return

    # "beni ara" -> sahibin telefonunu ara (sadece kayıtlı numara)
    if intents.match_call_me_intent(text):
        await manager.broadcast({"type": "tool_start", "name": "call_my_phone", "args": {}})
        result = await asyncio.to_thread(telephony.call_owner)
        await manager.broadcast({"type": "tool_end", "name": "call_my_phone", "success": True})
        await log_message("sys", f"JRV: {result}")
        await sm.enqueue_sentence(result.split(". ")[0])
        await manager.broadcast({"type": "status", "value": "ONLINE"})
        return

    buffer = sm.SentenceBuffer()
    
    # Store the task in state so it can be cancelled
    async def ai_stream():
        full_text = ""
        try:
            async for chunk in am.generate_response_stream(text):
                if chunk["type"] == "token":
                    full_text += chunk["content"]
                    await manager.broadcast({"type": "token", "content": chunk["content"]})
                    await buffer.add_token(chunk["content"])
                elif chunk["type"] == "tool_call":
                    await manager.broadcast({"type": "tool_start", "name": chunk["name"], "args": chunk["args"]})
                elif chunk["type"] == "tool_result":
                    await manager.broadcast({"type": "tool_end", "name": chunk["name"], "success": True})
                elif chunk["type"] == "error":
                    await send_error(chunk["content"])

            await buffer.flush()
            await manager.broadcast({"type": "status", "value": "ONLINE"})
        except asyncio.CancelledError:
            print("[AI STREAM] Task cancelled by barge-in.")
            await send_error("[Interrupted]")
            await manager.broadcast({"type": "status", "value": "ONLINE"})
        except Exception as e:
            print(f"[AI STREAM ERROR] {e}")
            await send_error(f"LLM Error: {str(e)}")
            await manager.broadcast({"type": "status", "value": "ONLINE"})
        finally:
            if full_text.strip():
                chat_history.append({"sender": "sys", "text": f"JRV: {full_text}"})

    task = asyncio.create_task(ai_stream())
    state.register_task("ai_stream_task", task)

async def send_error(message: str):
    chat_history.append({"sender": "err", "text": f"ERR: {message}"})
    await manager.broadcast({"type": "error", "message": message})

async def run_claude_intent(intent: dict):
    await manager.broadcast({"type": "tool_start", "name": "open_claude", "args": intent})
    try:
        result = await asyncio.to_thread(claude_launcher.open_claude, intent["mode"], intent.get("project_name"))
    except Exception as e:
        result = f"Claude açılamadı: {e}"
    await manager.broadcast({"type": "tool_end", "name": "open_claude", "success": True})
    await log_message("sys", f"JRV: {result}")
    # TTS'e yolları okutma, sadece ilk cümleyi söyle
    await sm.enqueue_sentence(result.split(". ")[0])
    await manager.broadcast({"type": "status", "value": "ONLINE"})

# Background thread for listening to the microphone
def audio_listener_loop():
    mic_error_reported = False
    while True:
        if not state.mic_active:
            time.sleep(0.5)
            continue

        def on_hearing():
            safe_broadcast({"type": "status", "value": "HEARING"})

        try:
            text = sm.listen(on_speech_start=on_hearing)
            if mic_error_reported:
                mic_error_reported = False
                safe_broadcast({"type": "log", "sender": "sys", "text": "SYS: Mikrofon tekrar çalışıyor."})
            if text:
                print(f"[AUDIO] Heard: {text}")
                # Dispatch the text processing into the main async loop
                if main_loop and main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(process_user_input(text), main_loop)
            elif text == "":
                # Ses geldi ama anlaşılamadı: kullanıcı en azından mikrofonun çalıştığını görsün
                safe_broadcast({"type": "log", "sender": "sys", "text": "SYS: Sesini duydum ama anlayamadım, tekrar söyler misin?"})
                safe_broadcast({"type": "status", "value": "ONLINE"})
        except sm.MicrophoneError as e:
            # Eskiden bu hata sessizce yutuluyordu; artık arayüzde görünüyor
            if not mic_error_reported:
                mic_error_reported = True
                message = f"Mikrofon açılamadı: {e}. Windows ses ayarlarından mikrofonu/izni kontrol edin veya .env içinde JARVIS_MIC_DEVICE ayarlayın."
                # Arayüz sonradan bağlansa da görsün diye geçmişe de yaz
                chat_history.append({"sender": "err", "text": f"ERR: {message}"})
                safe_broadcast({"type": "error", "message": message})
            time.sleep(5)
        except Exception as e:
            print(f"[AUDIO LOOP ERROR] {e}")
            time.sleep(1)

def vitals_loop():
    last_net = psutil.net_io_counters()
    last_time = time.time()
    while True:
        try:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            now_net = psutil.net_io_counters()
            now_time = time.time()
            dt = now_time - last_time
            if dt > 0:
                speed_kb = ((now_net.bytes_recv - last_net.bytes_recv) + (now_net.bytes_sent - last_net.bytes_sent)) / dt / 1024
            else:
                speed_kb = 0
            last_net = now_net
            last_time = now_time

            safe_broadcast({
                "type": "vitals",
                "cpu": cpu,
                "ram": ram,
                "net": speed_kb
            })
        except Exception as e:
            print(f"[VITALS ERROR] {e}")
        time.sleep(1)

def anti_laziness_loop():
    """Background daemon to monitor the active window and warn if slacking."""
    try:
        import pygetwindow as gw
    except ImportError:
        print("[ANTI-LAZINESS] pygetwindow not installed, skipping.")
        return
        
    lazy_keywords = ["youtube", "discord", "steam", "riot", "game", "twitter", "instagram"]
    slack_time = 0
    while True:
        try:
            active_win = gw.getActiveWindow()
            if active_win and active_win.title:
                title = active_win.title.lower()
                is_slacking = any(kw in title for kw in lazy_keywords)
                if is_slacking:
                    slack_time += 10
                else:
                    slack_time = max(0, slack_time - 10)
                    
                if slack_time >= 600: # 10 minutes of slacking
                    if main_loop and main_loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            process_user_input("Sir, I noticed you have been slacking off on social media or games for a while. Please scold me about productivity."),
                            main_loop
                        )
                    slack_time = 0 # reset after warning
        except Exception as e:
            pass
        time.sleep(10)

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()
    
    # Start the system tray
    tray_manager.start()
    
    # Start the async TTS worker
    asyncio.create_task(sm.speak_sentence_worker())
    
    # Define clap handler
    def on_clap():
        if main_loop and main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                process_user_input("Please welcome me briefly and enthusiastically."),
                main_loop
            )

    # Start background threads
    threading.Thread(target=audio_listener_loop, daemon=True).start()
    threading.Thread(target=telephony.sync_incoming_webhook, daemon=True).start()
    threading.Thread(target=vitals_loop, daemon=True).start()
    threading.Thread(target=anti_laziness_loop, daemon=True).start()
    # JARVIS_WAKE_WORD=0: "hey jarvis"/alkış dinleyicisini kapatır (mikrofonu ikinci kez açmaz)
    if wake_word is not None and os.getenv("JARVIS_WAKE_WORD", "1") != "0":
        threading.Thread(target=wake_word.start_wake_word_thread, args=(main_loop, manager.broadcast, on_clap), daemon=True).start()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Yeni bağlanan istemciye (ör. telefon) mevcut sohbeti ve mikrofon durumunu gönder
    await websocket.send_json({"type": "history", "messages": list(chat_history), "mic_active": state.mic_active})
    try:
        while True:
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                action = cmd.get("action")
                if action == "toggle_mic":
                    state.mic_active = cmd.get("state", True)
                    await manager.broadcast({"type": "mic_state", "value": state.mic_active})
                elif action == "interrupt":
                    state.cancel_all_barge_in_tasks()
                    sm.clear_speech_queue()
                elif action == "chat":
                    text = cmd.get("text", "")
                    if text:
                        await process_user_input(text)
            except json.JSONDecodeError as e:
                print(f"[WS JSON ERROR] Could not parse message: {data}")
            except Exception as e:
                print(f"[WS LOGIC ERROR] {e}")
                await manager.broadcast({"type": "error", "message": f"Server Error: {str(e)}"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS FATAL ERROR] {e}")
        manager.disconnect(websocket)

# ---------------------------------------------------------
# PHONE (Twilio) - normal telefon araması
# ---------------------------------------------------------
# PIN doğrulanmış aramalar (CallSid) ve PIN'den sonra söylenecek arama sebepleri
verified_calls = set()
pending_intros = {}

def _twiml_response(xml: str) -> Response:
    return Response(content=xml, media_type="application/xml")

async def _twilio_params(request: Request):
    """Returns the form params if the request is a genuine Twilio request from/to the owner, else None."""
    params = dict(await request.form())
    path_and_query = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    if not telephony.validate_twilio_request(path_and_query, params, request.headers.get("X-Twilio-Signature")):
        print(f"[PHONE] Rejected request with invalid Twilio signature: {path_and_query}")
        return None
    if not telephony.is_owner(telephony.caller_of(params)):
        print(f"[PHONE] Rejected call from/to a number that is not the owner: {telephony.caller_of(params)}")
        return None
    return params

def _call_allowed(params: dict) -> bool:
    return not telephony.pin() or params.get("CallSid") in verified_calls

@app.post("/phone/voice")
async def phone_voice(request: Request):
    params = await _twilio_params(request)
    if params is None:
        return _twiml_response(telephony.reject())
    intro = request.query_params.get("intro")
    await log_message("sys", "SYS: 📞 Telefon görüşmesi başladı.")
    if telephony.pin():
        # Outbound intro PIN'den sonra söylenir
        if intro:
            pending_intros[params.get("CallSid", "")] = intro
        return _twiml_response(telephony.ask_pin())
    return _twiml_response(telephony.greet(intro))

@app.post("/phone/pin")
async def phone_pin(request: Request):
    params = await _twilio_params(request)
    if params is None:
        return _twiml_response(telephony.hangup())
    call_sid = params.get("CallSid", "")
    if params.get("Digits", "") == telephony.pin():
        verified_calls.add(call_sid)
        return _twiml_response(telephony.greet(pending_intros.pop(call_sid, None)))
    await log_message("err", "ERR: 📞 Telefonda yanlış PIN girildi, arama kapatıldı.")
    return _twiml_response(telephony.say_and_hangup("PIN hatalı. Görüşmek üzere."))

@app.post("/phone/listen")
async def phone_listen(request: Request):
    params = await _twilio_params(request)
    if params is None or not _call_allowed(params):
        return _twiml_response(telephony.hangup())
    return _twiml_response(telephony.listen_again())

@app.post("/phone/speech")
async def phone_speech(request: Request):
    params = await _twilio_params(request)
    if params is None or not _call_allowed(params):
        return _twiml_response(telephony.hangup())
    text = (params.get("SpeechResult") or "").strip()
    if not text:
        return _twiml_response(telephony.listen_again("Sizi duyamadım, tekrar söyler misiniz?"))
    await log_message("user", f"📞 USR: {text}")
    if telephony.is_hangup(text):
        verified_calls.discard(params.get("CallSid"))
        await log_message("sys", "SYS: 📞 Telefon görüşmesi bitti.")
        return _twiml_response(telephony.say_and_hangup("Görüşmek üzere efendim."))
    try:
        # Twilio yaklaşık 15 sn cevap bekliyor
        answer = await asyncio.wait_for(
            am.generate_text(text, allow_tools=telephony.tools_allowed(), extra_instruction=telephony.PHONE_INSTRUCTION),
            timeout=12,
        )
    except asyncio.TimeoutError:
        answer = ""
    if not answer:
        answer = "Şu an cevap veremedim, tekrar sorar mısınız?"
    await log_message("sys", f"📞 JRV: {answer}")
    return _twiml_response(telephony.reply(answer))

@app.get("/api/minimize")
async def minimize_ui():
    await manager.broadcast({"type": "action", "value": "minimize"})
    return {"status": "ok"}

@app.get("/api/protocol/{protocol_name}")
async def set_protocol(protocol_name: str):
    state.protocol = protocol_name
    await manager.broadcast({"type": "action", "value": "protocol", "protocol_name": protocol_name})
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
