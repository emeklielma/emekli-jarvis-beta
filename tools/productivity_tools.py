import time
import threading
import urllib.request
import json
import urllib.parse
from tools.registry import register_tool
from core import speech_module as sm

@register_tool(
    name="set_reminder",
    description="Sets a reminder that will trigger after a specified number of minutes. Jarvis will verbally remind the user.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "minutes": {"type": "INTEGER", "description": "Minutes to wait before reminding."},
            "message": {"type": "STRING", "description": "The reminder message to speak."}
        },
        "required": ["minutes", "message"]
    }
)
def set_reminder(minutes: int, message: str) -> str:
    def reminder_thread(m, msg):
        time.sleep(m * 60)
        # We need to run the async enqueue in the event loop, but since we are in a thread, we'll just use a hack or the safe broadcast
        # Actually, speech_module might have a blocking TTS for this or we can create a new event loop.
        # Let's just generate the audio and play it directly for the reminder.
        import edge_tts
        import asyncio
        import ctypes
        import os
        
        async def speak_it():
            temp_audio = f"reminder_{int(time.time())}.mp3"
            communicate = edge_tts.Communicate(f"Sir, here is your reminder: {msg}", 'en-GB-RyanNeural')
            await communicate.save(temp_audio)
            
            mci = ctypes.windll.winmm.mciSendStringW
            alias = f"media_{int(time.time())}"
            mci(f'open "{temp_audio}" alias {alias}', None, 0, None)
            mci(f'play {alias} wait', None, 0, None)
            mci(f'close {alias}', None, 0, None)
            if os.path.exists(temp_audio):
                try: os.remove(temp_audio)
                except: pass
                
        asyncio.run(speak_it())

    t = threading.Thread(target=reminder_thread, args=(minutes, message), daemon=True)
    t.start()
    return f"Reminder set for {minutes} minutes from now."

@register_tool(
    name="fetch_news",
    description="Fetches the top news headlines for today.",
)
def fetch_news() -> str:
    try:
        # We can use a public news RSS or API. Let's use duckduckgo search for 'top news'
        req = urllib.request.Request("https://html.duckduckgo.com/html/?q=top+news+headlines", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
        
        import re
        snippets = re.findall(r'class="result__snippet[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        clean_snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets]
        
        if clean_snippets:
            return "Here are the top news headlines:\n" + "\n".join(f"- {s}" for s in clean_snippets[:5])
        return "Could not fetch news at the moment."
    except Exception as e:
        return f"Failed to fetch news: {e}"
