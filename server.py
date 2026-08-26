import os
import asyncio
import threading
import subprocess
import time
import json
import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
from core import wake_word
from core.tray import tray_manager

app = FastAPI()

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
    await manager.broadcast({"type": "log", "sender": "user", "text": f"USR: {text}"})
    await manager.broadcast({"type": "status", "value": "THINKING"})
    
    # Send start marker for Jarvis response
    await manager.broadcast({"type": "log", "sender": "sys", "text": "JRV: "})
    
    buffer = sm.SentenceBuffer()
    
    # Store the task in state so it can be cancelled
    async def ai_stream():
        try:
            async for chunk in am.generate_response_stream(text):
                if chunk["type"] == "token":
                    await manager.broadcast({"type": "token", "content": chunk["content"]})
                    await buffer.add_token(chunk["content"])
                elif chunk["type"] == "tool_call":
                    await manager.broadcast({"type": "tool_start", "name": chunk["name"], "args": chunk["args"]})
                elif chunk["type"] == "tool_result":
                    await manager.broadcast({"type": "tool_end", "name": chunk["name"], "success": True})
                elif chunk["type"] == "error":
                    await manager.broadcast({"type": "error", "message": chunk["content"]})
                    
            await buffer.flush()
            await manager.broadcast({"type": "status", "value": "ONLINE"})
        except asyncio.CancelledError:
            print("[AI STREAM] Task cancelled by barge-in.")
            await manager.broadcast({"type": "error", "message": "[Interrupted]"})
            await manager.broadcast({"type": "status", "value": "ONLINE"})
        except Exception as e:
            print(f"[AI STREAM ERROR] {e}")
            await manager.broadcast({"type": "error", "message": f"LLM Error: {str(e)}"})
            await manager.broadcast({"type": "status", "value": "ONLINE"})

    task = asyncio.create_task(ai_stream())
    state.register_task("ai_stream_task", task)

# Background thread for listening to the microphone
def audio_listener_loop():
    while True:
        if not state.mic_active:
            time.sleep(0.5)
            continue
            
        def on_hearing():
            safe_broadcast({"type": "status", "value": "HEARING"})
            
        try:
            text = sm.listen(on_speech_start=on_hearing)
            if text:
                print(f"[AUDIO] Heard: {text}")
                # Dispatch the text processing into the main async loop
                if main_loop and main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(process_user_input(text), main_loop)
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
    threading.Thread(target=vitals_loop, daemon=True).start()
    threading.Thread(target=anti_laziness_loop, daemon=True).start()
    threading.Thread(target=wake_word.start_wake_word_thread, args=(main_loop, manager.broadcast, on_clap), daemon=True).start()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                action = cmd.get("action")
                if action == "toggle_mic":
                    state.mic_active = cmd.get("state", True)
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
