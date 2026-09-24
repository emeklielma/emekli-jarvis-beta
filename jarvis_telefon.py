"""
Jarvis Telefon: Linphone ile ücretsiz arama, herhangi bir Jarvis klasörünün yanında
TEK BAŞINA çalışır (o Jarvis'in koduna dokunmaz).

Gerekenler (aynı klasörde):
    sip_phone.py        (bu projedeki core/sip_phone.py)
    jarvis_telefon.py   (bu dosya)
    .env                -> JARVIS_SIP_USER, JARVIS_SIP_PASSWORD, JARVIS_SIP_OWNER
                           ve GEMINI_API_KEY (yoksa OLLAMA_MODEL ile yerel model)

Kullanım:
    python jarvis_telefon.py            -> hattı açar; Linphone'dan Jarvis'i arayabilirsin
    Pencerede "ara" yazıp Enter         -> Jarvis seni arar
    http://127.0.0.1:8431/call (POST)   -> başka programlar (ör. Jarvis) aramayı başlatabilir
"""

import json
import os
import re
import sys
import threading
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

SYSTEM_PROMPT = (
    "Sen J.A.R.V.I.S.'sin; sahibinle normal bir telefon görüşmesi yapıyorsun. Cevabın sesli okunacak: "
    "1-3 kısa cümle, madde işareti yok, emoji yok, link yok. Kullanıcı hangi dilde konuşursa o dilde cevap ver. "
    "Sahibine 'efendim' diye hitap et."
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


def ask_ai(messages: list) -> str:
    provider = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    order = {"gemini": [ask_gemini], "ollama": [ask_ollama]}.get(provider, [ask_gemini, ask_ollama])
    for backend in order:
        try:
            text = backend(messages)
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)  # qwen3 düşünce etiketleri
            text = re.sub(r"[*_#`]", "", text).strip()
            if text:
                return text
        except Exception as e:
            print(f"[AI] {backend.__name__} başarısız: {e}")
    return ""


def respond(text: str) -> str:
    with history_lock:
        history.append({"role": "user", "content": text})
        del history[:-MAX_TURNS * 2]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(history)
    answer = ask_ai(messages)
    if answer:
        with history_lock:
            history.append({"role": "assistant", "content": answer})
    return answer


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

    phone = sip_phone.SipPhone.from_env(respond=respond, log=log, on_call_start=new_call)
    phone.start()
    try:
        # Sadece bu bilgisayardan erişilebilir
        server = HTTPServer(("127.0.0.1", CONTROL_PORT), ControlHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    except OSError as e:
        print(f"[UYARI] Kontrol portu {CONTROL_PORT} açılamadı: {e}")

    print("=" * 50)
    print(" JARVIS TELEFON (Linphone)")
    print(f" Jarvis hesabı : {phone.user}@{phone.domain}")
    print(f" Sadece arayan/aranan : {phone.owner}")
    print(" Seni araması için: ara  yazıp Enter'a bas")
    print(" Çıkmak için      : q")
    print("=" * 50, flush=True)

    while True:
        try:
            command = input().strip()
        except (EOFError, KeyboardInterrupt):
            break
        if command.lower() in ("q", "çık", "cik", "exit"):
            break
        if command.lower().startswith("ara"):
            print(phone.call_owner(command[3:].strip()), flush=True)
    phone.stop()


phone = None

if __name__ == "__main__":
    main()
