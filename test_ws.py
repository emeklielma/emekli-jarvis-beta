import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected. Sending chat action...")
            await websocket.send(json.dumps({"action": "chat", "text": "Merhaba, test yapıyorum."}))
            
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                print(f"Received: {data}")
                
                # If we get ONLINE status and we already received thinking, we are probably done
                if data.get("type") == "status" and data.get("value") == "ONLINE":
                    print("Status returned to ONLINE. Stream completed successfully!")
                    break
    except Exception as e:
        print(f"Connection failed or timed out: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
