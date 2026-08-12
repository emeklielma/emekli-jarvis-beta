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

# Background thread to constantly listen for audio using Python!
def audio_listener_loop():
    # Use a new event loop for this thread to call async broadcast safely
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        # 1. Update UI to show we are listening via Python microphone
        loop.run_until_complete(manager.broadcast({"type": "status", "value": "LISTENING"}))
        
        try:
            # 2. This will block and use our flawless gapless queue to listen!
            text = sm.record_audio("temp.wav")
            
            if text:
                # 3. User said something, send it to UI
                loop.run_until_complete(manager.broadcast({"type": "log", "sender": "user", "text": f"USR: {text}"}))
                
                # 4. Change UI status to thinking
                loop.run_until_complete(manager.broadcast({"type": "status", "value": "THINKING"}))
                
                # 5. Generate AI response
                response = am.generate_response(text)
                
                # 6. Generate Neural Voice and tell UI to play it!
                timestamp = int(time.time() * 1000)
                clean_text = response.replace('"', '').replace("'", "")
                
                try:
                    os.makedirs("frontend/public", exist_ok=True)
                    subprocess.run(["edge-tts", "--text", clean_text, "--voice", "en-GB-RyanNeural", "--write-media", "frontend/public/response.mp3"], check=True)
                    
                    loop.run_until_complete(manager.broadcast({
                        "type": "log", 
                        "sender": "sys", 
                        "text": f"JRV: {response}",
                        "speak": True,
                        "audioUrl": f"/response.mp3?t={timestamp}"
                    }))
                except Exception as tts_err:
                    print("TTS Error:", tts_err)
                    loop.run_until_complete(manager.broadcast({
                        "type": "log", 
                        "sender": "sys", 
                        "text": f"JRV: {response}",
                        "speak": True
                    }))
                
        except Exception as e:
            print(f"Audio Error: {e}")
            loop.run_until_complete(manager.broadcast({"type": "log", "sender": "err", "text": f"ERR: Microphone failure."}))
            import time
            time.sleep(2) # Wait a bit before retrying if mic crashes

@app.on_event("startup")
async def startup_event():
    # Start the background audio listener thread automatically when server starts
    thread = threading.Thread(target=audio_listener_loop, daemon=True)
    thread.start()

# Live WebSocket for real-time UI updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
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
        subprocess.run(["edge-tts", "--text", clean_text, "--voice", "en-GB-RyanNeural", "--write-media", "frontend/public/response.mp3"], check=True)
        
        return {"response": response, "audioUrl": f"/response.mp3?t={timestamp}"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    print("=======================================")
    print(" JARVIS BRAIN ONLINE (FastAPI + WebSockets)")
    print("=======================================")
    uvicorn.run(app, host="0.0.0.0", port=8000)
