import os
import asyncio
import threading
import subprocess
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import ai_module as am
import speech_module as sm
import queue
import psutil

ui_queue = queue.Queue()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

MIC_ACTIVE = True
INTERRUPT_FLAG = False

def safe_broadcast(loop, message):
    try:
        loop.run_until_complete(manager.broadcast(message))
    except Exception as e:
        print(f"Broadcast error (ignored): {e}")

# Background thread to constantly listen for audio using Python!
def audio_listener_loop():
    while True:
        global MIC_ACTIVE, INTERRUPT_FLAG
        if not MIC_ACTIVE:
            time.sleep(0.5)
            continue
            
        INTERRUPT_FLAG = False
        
        # 1. Update UI to show we are listening via Python microphone
        ui_queue.put({"type": "status", "value": "LISTENING"})
        
        def on_hearing():
            ui_queue.put({"type": "status", "value": "HEARING"})
            
        try:
            # 2. This will block and use our flawless gapless queue to listen!
            text = sm.listen(on_speech_start=on_hearing)
            
            if INTERRUPT_FLAG:
                continue # User clicked interrupt!
                
            if text:
                # 3. User said something, send it to UI
                ui_queue.put({"type": "log", "sender": "user", "text": f"USR: {text}"})
                
                # 4. Change UI status to thinking
                ui_queue.put({"type": "status", "value": "THINKING"})
                
                # 5. Generate AI response
                response = am.generate_response(text)
                
                if INTERRUPT_FLAG:
                    continue # Interrupted during thinking!
                
                # 6. Generate Neural Voice and tell UI to play it!
                timestamp = int(time.time() * 1000)
                clean_text = response.replace('"', '').replace("'", "")
                
                try:
                    os.makedirs("frontend/public", exist_ok=True)
                    subprocess.run(["python", "-m", "edge_tts", "--text", clean_text, "--voice", "en-GB-RyanNeural", "--write-media", "frontend/public/response.mp3"], check=True)
                    
                    ui_queue.put({
                        "type": "log", 
                        "sender": "sys", 
                        "text": f"JRV: {response}",
                        "speak": True,
                        "audioUrl": f"/response.mp3?t={timestamp}"
                    })
                except Exception as tts_err:
                    print("TTS Error:", tts_err)
                    ui_queue.put({
                        "type": "log", 
                        "sender": "sys", 
                        "text": f"JRV: {response}",
                        "speak": True
                    })
                
        except Exception as e:
            print(f"Audio Error: {e}")
            ui_queue.put({"type": "log", "sender": "err", "text": f"ERR: Microphone failure."})
            time.sleep(2) # Wait a bit before retrying if mic crashes

async def broadcast_worker():
    """Reads from ui_queue and safely broadcasts to websockets on the main event loop."""
    while True:
        try:
            while not ui_queue.empty():
                msg = ui_queue.get_nowait()
                await manager.broadcast(msg)
        except Exception:
            pass
        await asyncio.sleep(0.1)

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

            ui_queue.put({
                "type": "vitals",
                "cpu": cpu,
                "ram": ram,
                "net": speed_kb
            })
        except Exception:
            time.sleep(1)

@app.on_event("startup")
async def startup_event():
    # Start the robust UI broadcast worker in the main async loop
    asyncio.create_task(broadcast_worker())
    
    # Start the background audio listener thread automatically when server starts
    thread = threading.Thread(target=audio_listener_loop, daemon=True)
    thread.start()

    # Start the system vitals loop
    vitals_thread = threading.Thread(target=vitals_loop, daemon=True)
    vitals_thread.start()

# Live WebSocket for real-time UI updates
import json

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    global MIC_ACTIVE, INTERRUPT_FLAG
    try:
        while True:
            # Receive commands from the UI
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                if cmd.get("action") == "toggle_mic":
                    MIC_ACTIVE = cmd.get("state", True)
                    print(f"Microphone Active: {MIC_ACTIVE}")
                elif cmd.get("action") == "interrupt":
                    INTERRUPT_FLAG = True
                    print("User interrupted!")
            except:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Standard endpoint for manual typing
class ChatRequest(BaseModel):
    text: str

@app.post("/api/chat")
def chat(request: ChatRequest):
    try:
        response = am.generate_response(request.text)
        
        timestamp = int(time.time() * 1000)
        clean_text = response.replace('"', '').replace("'", "")
        os.makedirs("frontend/public", exist_ok=True)
        subprocess.run(["python", "-m", "edge_tts", "--text", clean_text, "--voice", "en-GB-RyanNeural", "--write-media", "frontend/public/response.mp3"], check=True)
        
        return {"response": response, "audioUrl": f"/response.mp3?t={timestamp}"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/minimize")
async def minimize_ui():
    ui_queue.put({"type": "action", "value": "minimize"})
    return {"status": "ok"}

@app.get("/api/protocol/{protocol_name}")
async def set_protocol(protocol_name: str):
    ui_queue.put({"type": "action", "value": "protocol", "protocol_name": protocol_name})
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    print("=======================================")
    print(" JARVIS BRAIN ONLINE (FastAPI + WebSockets)")
    print("=======================================")
    uvicorn.run(app, host="0.0.0.0", port=8000)
