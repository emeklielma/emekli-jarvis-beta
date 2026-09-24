"""
J.A.R.V.I.S. telefon hattı (Twilio, normal GSM araması - WhatsApp değil).

- Jarvis SADECE sahibinin numarasını (JARVIS_OWNER_PHONE) arayabilir; arama
  fonksiyonu başka numara parametresi almaz.
- Jarvis'in numarasını sadece sahibi arayabilir; diğer arayanlar reddedilir.
- Twilio'dan gelen her istek X-Twilio-Signature ile doğrulanır.

Gerekli .env ayarları:
    TWILIO_ACCOUNT_SID=AC...
    TWILIO_AUTH_TOKEN=...
    TWILIO_PHONE_NUMBER=+1...          (Twilio'dan alınan Jarvis numarası)
    JARVIS_OWNER_PHONE=+905XXXXXXXXX   (senin numaran; 05XX... de yazılabilir)
    JARVIS_PUBLIC_URL=https://....ngrok-free.app   (Twilio'nun server.py'ye ulaştığı adres)
İsteğe bağlı:
    JARVIS_PHONE_PIN=1234        (aramada önce tuşlarla PIN sorulur)
    JARVIS_PHONE_TOOLS=1         (telefondan bilgisayar araçlarını kullanmaya izin ver; PIN şart)
    JARVIS_PHONE_VOICE=Polly.Filiz
    JARVIS_PHONE_LANG=tr-TR
"""

import os
import re
from typing import Optional
from urllib.parse import quote, urlsplit

from dotenv import load_dotenv

load_dotenv()

HANGUP_WORDS = ("görüşürüz", "hoşça kal", "hoşçakal", "güle güle", "kapat", "kapatabilirsin",
                "bye", "goodbye", "hang up")

PHONE_INSTRUCTION = (
    "[PHONE CALL MODE] You are talking to your owner over a normal phone call. Your reply will be "
    "read aloud by a text-to-speech voice: answer in 1-3 short spoken sentences, no markdown, no lists, "
    "no emojis, no URLs. Reply in the language the user speaks."
)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def normalize_number(number: str) -> str:
    """'0532 123 45 67', '905321234567', '+90 532...' -> '+905321234567'."""
    if not number:
        return ""
    digits = re.sub(r"\D", "", number)
    if digits.startswith("00"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):   # 05XX XXX XX XX (Türkiye)
        digits = "90" + digits[1:]
    elif len(digits) == 10 and digits.startswith("5"):   # 5XX XXX XX XX (Türkiye)
        digits = "90" + digits
    return "+" + digits if digits else ""


def owner_number() -> str:
    return normalize_number(_env("JARVIS_OWNER_PHONE"))


def jarvis_number() -> str:
    return normalize_number(_env("TWILIO_PHONE_NUMBER"))


def public_url() -> str:
    return _env("JARVIS_PUBLIC_URL").rstrip("/")


def public_host() -> str:
    url = public_url()
    return urlsplit(url).netloc.lower() if url else ""


def voice() -> str:
    return _env("JARVIS_PHONE_VOICE", "Polly.Filiz")


def language() -> str:
    return _env("JARVIS_PHONE_LANG", "tr-TR")


def pin() -> str:
    return re.sub(r"\D", "", _env("JARVIS_PHONE_PIN"))


def tools_allowed() -> bool:
    # Arayan numara taklit edilebildiği için bilgisayar araçları sadece PIN ile açılabilir
    return _env("JARVIS_PHONE_TOOLS") == "1" and bool(pin())


def missing_config() -> list:
    required = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
                "JARVIS_OWNER_PHONE", "JARVIS_PUBLIC_URL"]
    return [name for name in required if not _env(name)]


def is_configured() -> bool:
    return not missing_config()


def is_owner(number: str) -> bool:
    owner = owner_number()
    return bool(owner) and normalize_number(number) == owner


def is_hangup(text: str) -> bool:
    t = (text or "").lower()
    return any(word in t for word in HANGUP_WORDS)


# ---------------------------------------------------------
# REQUEST VALIDATION
# ---------------------------------------------------------

def validate_twilio_request(path_and_query: str, params: dict, signature: Optional[str]) -> bool:
    """Checks X-Twilio-Signature. Twilio signs the public URL it called, so the URL is
    rebuilt from JARVIS_PUBLIC_URL (the local server only sees localhost behind the tunnel)."""
    token = _env("TWILIO_AUTH_TOKEN")
    if not token or not signature or not public_url():
        return False
    from twilio.request_validator import RequestValidator
    return RequestValidator(token).validate(public_url() + path_and_query, params, signature)


def caller_of(params: dict) -> str:
    """The owner's side of the call: 'From' for incoming calls, 'To' for calls Jarvis placed."""
    if params.get("Direction", "").startswith("outbound"):
        return params.get("To", "")
    return params.get("From", "")


# ---------------------------------------------------------
# TWIML
# ---------------------------------------------------------

def _twiml():
    from twilio.twiml.voice_response import VoiceResponse
    return VoiceResponse()


def _gather_speech(response, prompt: Optional[str]):
    gather = response.gather(input="speech", language=language(), speech_timeout="auto",
                             action="/phone/speech", method="POST")
    if prompt:
        gather.say(prompt, voice=voice(), language=language())
    # Hiç konuşulmazsa tekrar dinle
    response.redirect("/phone/listen", method="POST")
    return response


def reject() -> str:
    response = _twiml()
    response.reject()
    return str(response)


def hangup() -> str:
    """For requests during a call (Reject is only valid while the call is still ringing)."""
    response = _twiml()
    response.hangup()
    return str(response)


def say_and_hangup(text: str) -> str:
    response = _twiml()
    response.say(text, voice=voice(), language=language())
    response.hangup()
    return str(response)


def ask_pin() -> str:
    response = _twiml()
    gather = response.gather(input="dtmf", num_digits=len(pin()), timeout=10,
                             action="/phone/pin", method="POST")
    gather.say("Lütfen PIN kodunuzu tuşlayın.", voice=voice(), language=language())
    response.say("PIN girilmedi. Görüşmek üzere.", voice=voice(), language=language())
    response.hangup()
    return str(response)


def greet(intro: Optional[str] = None) -> str:
    return str(_gather_speech(_twiml(), intro or "Merhaba efendim, Jarvis dinliyor."))


def listen_again(prompt: Optional[str] = None) -> str:
    return str(_gather_speech(_twiml(), prompt))


def reply(text: str) -> str:
    return str(_gather_speech(_twiml(), text))


# ---------------------------------------------------------
# OUTBOUND CALL (sadece sahibin numarası)
# ---------------------------------------------------------

def _client():
    from twilio.rest import Client
    return Client(_env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN"))


def call_owner(reason: str = "") -> str:
    """Calls ONLY the owner's configured number. There is deliberately no 'number' argument."""
    missing = missing_config()
    if missing:
        return f"Telefon araması ayarlı değil. Eksik ayarlar: {', '.join(missing)}."
    intro = "Merhaba efendim, Jarvis arıyor."
    if reason:
        intro += " " + reason.strip()
    try:
        call = _client().calls.create(
            to=owner_number(),
            from_=jarvis_number(),
            url=f"{public_url()}/phone/voice?intro={quote(intro)}",
            method="POST",
        )
        print(f"[PHONE] Calling owner, call sid: {call.sid}")
        return "Telefonunuzu arıyorum."
    except Exception as e:
        print(f"[PHONE] Call failed: {e}")
        return f"Arama başlatılamadı: {e}"


def sync_incoming_webhook():
    """Points the Twilio number's incoming-call webhook at JARVIS_PUBLIC_URL/phone/voice,
    so the ngrok address in .env is all that has to be kept up to date."""
    if not is_configured():
        return
    try:
        numbers = _client().incoming_phone_numbers.list(phone_number=jarvis_number(), limit=1)
        if not numbers:
            print(f"[PHONE] {jarvis_number()} is not a number on this Twilio account.")
            return
        target = f"{public_url()}/phone/voice"
        if numbers[0].voice_url != target:
            numbers[0].update(voice_url=target, voice_method="POST")
            print(f"[PHONE] Incoming call webhook set to {target}")
    except Exception as e:
        print(f"[PHONE] Could not update the Twilio webhook: {e}")
