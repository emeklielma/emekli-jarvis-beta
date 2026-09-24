"""
Jarvis Telefon: Linphone ile ücretsiz arama, herhangi bir Jarvis klasörünün yanında
TEK BAŞINA çalışır (o Jarvis'in koduna dokunmaz).

Gerekenler (aynı klasörde):
    sip_phone.py        (bu projedeki core/sip_phone.py)
    jarvis_telefon.py   (bu dosya)
    .env                -> JARVIS_SIP_USER, JARVIS_SIP_PASSWORD, JARVIS_SIP_OWNER
                           ve GEMINI_API_KEY (yoksa OLLAMA_MODEL ile yerel model)

Ses / dil (.env, hepsi isteğe bağlı):
    JARVIS_PHONE_LANG=en-US             -> görüşme dili (varsayılan en-US; Türkçe için tr-TR)
    ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID -> Jarvis'in kendi ElevenLabs sesi (yoksa edge-tts)
    ELEVENLABS_MODEL_ID=eleven_flash_v2_5
Sesli komut: bilgisayarın mikrofonunda "call me" / "beni ara" duyulunca Jarvis seni arar
    (JARVIS_PHONE_HOTWORD=0 ile kapatılır).
Kamera: görüntülü aramada telefonun kamerası Jarvis'e gösterilir (pip install av pillow).

Kullanım:
    python jarvis_telefon.py            -> hattı açar; Linphone'dan Jarvis'i arayabilirsin
    Pencerede "ara" yazıp Enter         -> Jarvis seni arar
    http://127.0.0.1:8431/call (POST)   -> başka programlar (ör. Jarvis) aramayı başlatabilir
"""

import base64
import collections
import json
import os
import queue
import re
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
load_dotenv(os.path.join(HERE, ".env"))
sys.path.insert(0, HERE)

try:
    from core import sip_phone
except ImportError:
    import sip_phone

CONTROL_PORT = int(os.getenv("JARVIS_PHONE_CONTROL_PORT", "8431"))
MAX_TURNS = 10
PHONE_LANG = os.getenv("JARVIS_PHONE_LANG", "en-US").strip()
ENGLISH = PHONE_LANG.lower().startswith("en")
# sip_phone.default_stt / default_tts read these
os.environ["JARVIS_STT_LANG"] = PHONE_LANG
if not os.getenv("JARVIS_TTS_VOICE"):
    os.environ["JARVIS_TTS_VOICE"] = "en-GB-RyanNeural" if ENGLISH else "tr-TR-AhmetNeural"

if ENGLISH:
    SYSTEM_PROMPT = (
        "You are J.A.R.V.I.S., Tony Stark's loyal, witty British AI butler, on a normal phone call with your owner. "
        "Your reply is read aloud: 1-3 short sentences, no lists, no emojis, no links. Address him as 'sir'. "
        "If a picture from his phone camera is attached, that is what you can see right now; use it when he asks "
        "what you see or when it is relevant."
    )
else:
    SYSTEM_PROMPT = (
        "Sen J.A.R.V.I.S.'sin; sahibinle normal bir telefon görüşmesi yapıyorsun. Cevabın sesli okunacak: "
        "1-3 kısa cümle, madde işareti yok, emoji yok, link yok. Sahibine 'efendim' diye hitap et. "
        "Telefon kamerasından bir görüntü ekliyse şu an gördüğün odur; sorulduğunda ya da ilgiliyse kullan."
    )

history = []
history_lock = threading.Lock()


def _post_json(url: str, payload: dict, headers: dict, timeout: float = 20) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ask_gemini(messages: list) -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY yok")
    data = _post_json(
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        {"model": os.getenv("GEMINI_MODEL", "gemini-3.6-flash"), "messages": messages,
         "temperature": 0.4, "max_tokens": 300},
        {"Authorization": f"Bearer {key}"},
    )
    return data["choices"][0]["message"]["content"]


def ask_ollama(messages: list) -> str:
    model = os.getenv("OLLAMA_MODEL", "").strip()
    if not model:
        raise RuntimeError("OLLAMA_MODEL yok")
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    data = _post_json(f"{host}/api/chat", {"model": model, "messages": messages, "stream": False, "think": False}, {},
                      timeout=25)
    return data["message"]["content"]


def _with_image(messages: list, image: bytes) -> list:
    """Attaches the camera frame to the last user message (OpenAI-style content parts)."""
    url = "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")
    last = messages[-1]
    return messages[:-1] + [{"role": "user", "content": [{"type": "text", "text": last["content"]},
                                                         {"type": "image_url", "image_url": {"url": url}}]}]


def ask_ai(messages: list, image: bytes = None) -> str:
    provider = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    order = {"gemini": [ask_gemini], "ollama": [ask_ollama]}.get(provider, [ask_gemini, ask_ollama])
    for backend in order:
        try:
            # Yerel Ollama modeli (qwen3) görüntü görmez; görüntü sadece Gemini'ye gider
            text = backend(_with_image(messages, image) if image and backend is ask_gemini else messages)
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)  # qwen3 düşünce etiketleri
            text = re.sub(r"[*_#`]", "", text).strip()
            if text:
                return text
        except Exception as e:
            print(f"[AI] {backend.__name__} başarısız: {e}")
    return ""


def respond(text: str, image: bytes = None) -> str:
    with history_lock:
        history.append({"role": "user", "content": text})
        del history[:-MAX_TURNS * 2]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(history)
    if image:
        print("[KAMERA] Görüntü Jarvis'e gönderildi.", flush=True)
    answer = ask_ai(messages, image)
    if answer:
        with history_lock:
            history.append({"role": "assistant", "content": answer})
    return answer


def elevenlabs_tts(text: str):
    """Jarvis'in kendi ElevenLabs sesi, doğrudan telefon formatında (8 kHz u-law)."""
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    voice = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=ulaw_8000",
        data=json.dumps({"text": text, "model_id": os.getenv("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/basic"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return sip_phone.g711_decode(resp.read(), 0)


def tts(text: str):
    if os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID"):
        try:
            return elevenlabs_tts(text)
        except Exception as e:
            print(f"[SES] ElevenLabs başarısız, yedek sese geçiliyor: {e}", flush=True)
    return sip_phone.default_tts(text)


CALL_PHRASES = ("call me", "call my phone", "ring me", "phone me", "beni ara", "telefonumu ara")
HOTWORD_COOLDOWN = 20


def is_call_request(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in CALL_PHRASES)


def hotword_loop():
    """Bilgisayar mikrofonunu dinler; 'call me' / 'beni ara' duyunca sahibini arar."""
    try:
        import numpy as np
        import sounddevice as sd
        import speech_recognition as sr
    except Exception as e:
        print(f"[SESLİ KOMUT] Kapalı ({e}).", flush=True)
        return
    rate, block = 16000, 4000                       # 0.25 s parçalar
    chunks: "queue.Queue" = queue.Queue()
    recognizer = sr.Recognizer()
    last_call = 0.0

    def handle(pcm):
        nonlocal last_call
        try:
            text = recognizer.recognize_google(sr.AudioData(pcm.tobytes(), rate, 2), language=PHONE_LANG)
        except Exception:
            return
        if is_call_request(text) and time.time() - last_call > HOTWORD_COOLDOWN and not phone.calls:
            last_call = time.time()
            print(f'[SESLİ KOMUT] "{text}" -> {phone.call_owner()}', flush=True)

    while True:
        try:
            with sd.InputStream(samplerate=rate, channels=1, dtype="int16", blocksize=block,
                                callback=lambda data, frames, t, status: chunks.put(data[:, 0].copy())):
                print('[SESLİ KOMUT] Dinliyorum: "Jarvis, call me" deyince seni ararım.', flush=True)
                noise, talking, silence, buffer = None, False, 0, []
                preroll = collections.deque(maxlen=2)
                while True:
                    chunk = chunks.get()
                    if phone.calls:                     # görüşme sırasında dinleme
                        talking, buffer = False, []
                        continue
                    level = float(np.sqrt(np.mean((chunk / 32768.0) ** 2)))
                    noise = level if noise is None else noise
                    if level > max(noise * 3.0, 0.01):
                        if not talking:
                            talking, buffer = True, list(preroll)
                        buffer.append(chunk)
                        silence = 0
                    elif talking:
                        buffer.append(chunk)
                        silence += 1
                        if silence >= 3 or len(buffer) > 32:   # 0.75 s sessizlik / en fazla 8 s
                            pcm, talking, buffer = np.concatenate(buffer), False, []
                            threading.Thread(target=handle, args=(pcm,), daemon=True).start()
                    else:
                        noise = 0.95 * noise + 0.05 * level
                        preroll.append(chunk)
        except Exception as e:
            print(f"[SESLİ KOMUT] Mikrofon açılamadı: {e}. 10 sn sonra tekrar denenecek.", flush=True)
            time.sleep(10)


def new_call():
    with history_lock:
        history.clear()


def log(sender: str, text: str):
    print(text, flush=True)


class ControlHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.split("?")[0] != "/call":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        reason = ""
        if length:
            try:
                reason = json.loads(self.rfile.read(length)).get("reason", "")
            except Exception:
                pass
        result = phone.call_owner(reason)
        body = json.dumps({"result": result}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    global phone
    missing = sip_phone.missing_config()
    if missing:
        print(f"[HATA] .env dosyasında eksik: {', '.join(missing)}")
        input("Kapatmak için Enter'a basın...")
        return
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("OLLAMA_MODEL"):
        print("[UYARI] .env'de GEMINI_API_KEY veya OLLAMA_MODEL yok; Jarvis telefonda cevap veremez.")

    video = sip_phone.video_available()
    phone = sip_phone.SipPhone.from_env(respond=respond, log=log, on_call_start=new_call, tts=tts,
                                        lang=PHONE_LANG, video=video)
    phone.start()
    try:
        # Sadece bu bilgisayardan erişilebilir
        server = HTTPServer(("127.0.0.1", CONTROL_PORT), ControlHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    except OSError as e:
        print(f"[UYARI] Kontrol portu {CONTROL_PORT} açılamadı: {e}")

    if os.getenv("JARVIS_PHONE_HOTWORD", "1") != "0":
        threading.Thread(target=hotword_loop, daemon=True).start()

    print("=" * 50)
    print(" JARVIS TELEFON (Linphone)")
    print(f" Jarvis hesabı : {phone.user}@{phone.domain}")
    print(f" Sadece arayan/aranan : {phone.owner}")
    voice = "ElevenLabs" if os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID") else os.environ["JARVIS_TTS_VOICE"]
    print(f" Dil / ses    : {PHONE_LANG} / {voice}")
    print(f" Kamera       : {'açık (görüntülü aramada Jarvis görür)' if video else 'kapalı (pip install av pillow)'}")
    print(" Seni araması için: \"Jarvis, call me\" de  ya da  ara  yazıp Enter'a bas")
    print(" Çıkmak için      : q")
    print("=" * 50, flush=True)

    while True:
        try:
            command = input().strip()
        except (EOFError, KeyboardInterrupt):
            break
        if command.lower() in ("q", "çık", "cik", "exit"):
            break
        lowered = command.lower()
        if "ara" in lowered.split() or lowered.startswith("ara") or "call" in lowered:
            print(phone.call_owner(), flush=True)
        elif command:
            print("Jarvis'in seni araması için 'ara' yazıp Enter'a bas.", flush=True)
    phone.stop()


phone = None

if __name__ == "__main__":
    main()
