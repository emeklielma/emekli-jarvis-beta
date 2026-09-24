"""
J.A.R.V.I.S. Linphone hattı: ücretsiz internet araması (SIP).

Jarvis bilgisayarda kendi Linphone hesabıyla (sip.linphone.org) bir SIP telefonu
gibi çalışır:
  - Sadece sahibinin Linphone hesabını (JARVIS_SIP_OWNER) arayabilir.
  - Sadece sahibinden gelen aramaları açar; diğerleri reddedilir.
  - Görüşmede sesi yazıya çevirir (Google), Gemini ile cevaplar ve edge-tts ile konuşur.

Gerekli .env ayarları:
    JARVIS_SIP_USER=jarvis-kullanici-adi      (Jarvis'in Linphone hesabı)
    JARVIS_SIP_PASSWORD=...
    JARVIS_SIP_OWNER=senin-linphone-adin      (telefonundaki Linphone hesabı)
İsteğe bağlı:
    JARVIS_SIP_DOMAIN=sip.linphone.org
    JARVIS_SIP_PROXY=host:port               (varsayılan: domain:5060)
    JARVIS_SIP_PORT=5070                     (bilgisayarda kullanılacak UDP portu)

Sadece UDP ve G.711 (PCMU/PCMA) kullanır; ICE/STUN yoktur. Bu yüzden en
güvenilir çalıştığı durum telefon ve bilgisayarın aynı Wi-Fi'da olmasıdır.
"""

import asyncio
import collections
import hashlib
import io
import os
import queue
import random
import re
import socket
import string
import struct
import threading
import time
from typing import Callable, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv

load_dotenv()

USER_AGENT = "Jarvis-SIP/1.0"
RING_TIMEOUT = 45          # saniye; açılmazsa arama iptal edilir
T1, T2 = 0.5, 4.0          # SIP yeniden gönderme zamanlayıcıları (RFC 3261)
REGISTER_EXPIRES = 300
KEEPALIVE_SECONDS = 20
FRAME = 160                # 20 ms @ 8 kHz
SAMPLE_RATE = 8000

HANGUP_WORDS = ("görüşürüz", "hoşça kal", "hoşçakal", "güle güle", "kapat", "kapatabilirsin",
                "bye", "goodbye", "hang up")


def is_hangup(text: str) -> bool:
    t = (text or "").lower()
    return any(word in t for word in HANGUP_WORDS)


# Ayarlanmışsa server.py başlatınca buraya koyar (tools/phone_tools.py kullanır)
instance: Optional["SipPhone"] = None


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def missing_config() -> List[str]:
    return [n for n in ("JARVIS_SIP_USER", "JARVIS_SIP_PASSWORD", "JARVIS_SIP_OWNER") if not _env(n)]


def is_configured() -> bool:
    return not missing_config()


def _rand(n: int = 10) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def normalize_address(value: str, default_domain: str) -> str:
    """'Aras', 'sip:aras@sip.linphone.org', 'aras@sip.linphone.org' -> 'aras@sip.linphone.org'."""
    value = value.strip().lower()
    value = re.sub(r"^sips?:", "", value)
    value = value.split(";", 1)[0]
    if "@" not in value:
        value = f"{value}@{default_domain.lower()}"
    user, _, host = value.partition("@")
    return f"{user}@{host.split(':', 1)[0]}"


# ---------------------------------------------------------
# G.711 (PCMU / PCMA) - audioop Python 3.13'te kaldırıldığı için kendi tablolarımız
# ---------------------------------------------------------

def _ulaw_decode_table() -> np.ndarray:
    table = np.zeros(256, dtype=np.int16)
    for i in range(256):
        u = ~i & 0xFF
        exponent = (u >> 4) & 0x07
        sample = (((u & 0x0F) << 3) + 0x84) << exponent
        sample -= 0x84
        table[i] = -sample if u & 0x80 else sample
    return table


def _alaw_decode_table() -> np.ndarray:
    table = np.zeros(256, dtype=np.int16)
    for i in range(256):
        a = i ^ 0x55
        exponent = (a >> 4) & 0x07
        mantissa = a & 0x0F
        sample = (mantissa << 4) + 8 if exponent == 0 else ((mantissa << 4) + 0x108) << (exponent - 1)
        table[i] = sample if a & 0x80 else -sample
    return table


def _encode_table(decode: np.ndarray) -> np.ndarray:
    """16-bit PCM -> nearest G.711 code, as a 65536-entry lookup table."""
    order = np.argsort(decode, kind="stable")
    values = decode[order].astype(np.int32)
    pcm = np.arange(-32768, 32768, dtype=np.int32)
    idx = np.clip(np.searchsorted(values, pcm), 1, 255)
    left, right = values[idx - 1], values[idx]
    idx = np.where(np.abs(pcm - left) <= np.abs(right - pcm), idx - 1, idx)
    return order[idx].astype(np.uint8)


_DECODE = {0: _ulaw_decode_table(), 8: _alaw_decode_table()}
_ENCODE = {pt: _encode_table(table) for pt, table in _DECODE.items()}
_SILENCE = {0: 0xFF, 8: 0xD5}


def g711_encode(pcm: np.ndarray, pt: int) -> bytes:
    return _ENCODE[pt][pcm.astype(np.int32) + 32768].tobytes()


def g711_decode(payload: bytes, pt: int) -> np.ndarray:
    return _DECODE[pt][np.frombuffer(payload, dtype=np.uint8)]


def resample_to_8k(samples: np.ndarray, rate: int) -> np.ndarray:
    """float32 mono -> int16 @ 8 kHz, with a windowed-sinc low-pass to avoid aliasing."""
    samples = samples.astype(np.float32)
    if rate != SAMPLE_RATE:
        cutoff = 3400 / rate
        taps = 101
        n = np.arange(taps) - (taps - 1) / 2
        kernel = 2 * cutoff * np.sinc(2 * cutoff * n) * np.hamming(taps)
        filtered = np.convolve(samples, kernel / kernel.sum(), mode="same")
        positions = np.arange(0, len(samples), rate / SAMPLE_RATE)
        samples = np.interp(positions, np.arange(len(samples)), filtered)
    return (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)


# ---------------------------------------------------------
# SPEECH (varsayılan: Google STT + edge-tts)
# ---------------------------------------------------------

def default_stt(pcm: np.ndarray) -> str:
    import speech_recognition as sr
    audio = sr.AudioData(pcm.astype(np.int16).tobytes(), SAMPLE_RATE, 2)
    try:
        return sr.Recognizer().recognize_google(audio, language=_env("JARVIS_STT_LANG", "tr-TR"))
    except sr.UnknownValueError:
        return ""
    except Exception as e:
        print(f"[SIP] Speech recognition error: {e}")
        return ""


def default_tts(text: str) -> np.ndarray:
    import edge_tts
    import soundfile as sf
    try:
        from core.speech_module import pick_voice
    except ImportError:
        # Bu dosya Jarvis projesinin dışında tek başına kullanıldığında (jarvis_telefon.py)
        def pick_voice(t: str) -> str:
            return _env("JARVIS_TTS_VOICE") or "tr-TR-AhmetNeural"

    async def synth() -> bytes:
        data = bytearray()
        async for chunk in edge_tts.Communicate(text, pick_voice(text)).stream():
            if chunk["type"] == "audio":
                data.extend(chunk["data"])
        return bytes(data)

    mp3 = asyncio.run(synth())
    samples, rate = sf.read(io.BytesIO(mp3), dtype="float32")
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    return resample_to_8k(samples, rate)


# ---------------------------------------------------------
# SIP MESSAGE PARSING
# ---------------------------------------------------------

_COMPACT = {"v": "via", "f": "from", "t": "to", "i": "call-id", "m": "contact", "l": "content-length",
            "c": "content-type", "k": "supported"}
_MULTI = {"via", "record-route", "route", "contact"}


def _split_commas(value: str) -> List[str]:
    parts, depth, quoted, current = [], 0, False, ""
    for ch in value:
        if ch == '"':
            quoted = not quoted
        elif not quoted and ch == "<":
            depth += 1
        elif not quoted and ch == ">":
            depth -= 1
        if ch == "," and depth == 0 and not quoted:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


class SipMessage:
    def __init__(self, data: bytes):
        self.raw = data
        head, _, body = data.partition(b"\r\n\r\n")
        lines = head.decode("utf-8", "replace").split("\r\n")
        self.first_line = lines[0]
        self.headers: List[Tuple[str, str]] = []
        for line in lines[1:]:
            if line[:1] in (" ", "\t") and self.headers:
                name, value = self.headers[-1]
                self.headers[-1] = (name, value + " " + line.strip())
                continue
            name, _, value = line.partition(":")
            name = name.strip().lower()
            self.headers.append((_COMPACT.get(name, name), value.strip()))
        length = self.get("content-length")
        self.body = body[:int(length)] if length and length.isdigit() else body
        parts = self.first_line.split(" ", 2)
        self.is_response = parts[0].upper() == "SIP/2.0"
        if self.is_response:
            self.status = int(parts[1])
            self.reason = parts[2] if len(parts) > 2 else ""
            self.method, self.uri = None, None
        else:
            self.method, self.uri = parts[0].upper(), parts[1]
            self.status, self.reason = None, None

    def get(self, name: str) -> str:
        for n, v in self.headers:
            if n == name:
                return _split_commas(v)[0] if n in _MULTI else v
        return ""

    def get_all(self, name: str) -> List[str]:
        values = []
        for n, v in self.headers:
            if n == name:
                values.extend(_split_commas(v) if n in _MULTI else [v])
        return values

    @property
    def cseq(self) -> Tuple[int, str]:
        num, _, method = self.get("cseq").partition(" ")
        return int(num or 0), method.strip().upper()

    @property
    def branch(self) -> str:
        m = re.search(r";\s*branch=([^;,\s]+)", self.get("via"))
        return m.group(1) if m else ""


def uri_of(header_value: str) -> str:
    m = re.search(r"<([^>]*)>", header_value)
    return m.group(1) if m else header_value.split(";", 1)[0].strip()


def tag_of(header_value: str) -> str:
    rest = header_value.split(">", 1)[1] if ">" in header_value else header_value
    m = re.search(r";\s*tag=([^;\s]+)", rest)
    return m.group(1) if m else ""


def _via_params(via: str) -> dict:
    return {k.lower(): v for k, v in re.findall(r";\s*([\w-]+)(?:=([^;\s]+))?", via)}


def build_message(first_line: str, headers: List[Tuple[str, str]], body: bytes = b"") -> bytes:
    lines = [first_line] + [f"{k}: {v}" for k, v in headers]
    lines += [f"Content-Length: {len(body)}", "", ""]
    return "\r\n".join(lines).encode("utf-8") + body


def digest_authorization(challenge_response: SipMessage, method: str, uri: str, user: str, password: str) -> Tuple[str, str]:
    """Answers a 401/407 challenge (MD5 or SHA-256, with or without qop=auth)."""
    header = "www-authenticate" if challenge_response.status == 401 else "proxy-authenticate"
    challenges = []
    for value in challenge_response.get_all(header):
        params = {k.lower(): (q if q else u) for k, q, u in re.findall(r'(\w+)=(?:"([^"]*)"|([^,\s]+))', value)}
        challenges.append(params)
    if not challenges:
        raise ValueError("No authentication challenge")
    # Prefer SHA-256 if the server offers it
    chal = next((c for c in challenges if c.get("algorithm", "").upper() == "SHA-256"), challenges[0])
    algorithm = chal.get("algorithm", "MD5").upper()
    h = (lambda s: hashlib.sha256(s.encode()).hexdigest()) if algorithm == "SHA-256" else (lambda s: hashlib.md5(s.encode()).hexdigest())
    realm, nonce = chal.get("realm", ""), chal.get("nonce", "")
    ha1 = h(f"{user}:{realm}:{password}")
    ha2 = h(f"{method}:{uri}")
    fields = f'username="{user}", realm="{realm}", nonce="{nonce}", uri="{uri}", algorithm={algorithm}'
    if "auth" in [q.strip() for q in chal.get("qop", "").split(",")]:
        cnonce, nc = _rand(16), "00000001"
        response = h(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}")
        fields += f', qop=auth, nc={nc}, cnonce="{cnonce}"'
    else:
        response = h(f"{ha1}:{nonce}:{ha2}")
    fields += f', response="{response}"'
    if chal.get("opaque"):
        fields += f', opaque="{chal["opaque"]}"'
    name = "Authorization" if challenge_response.status == 401 else "Proxy-Authorization"
    return name, "Digest " + fields


ENCRYPTION_HINT = ("Telefondaki Linphone şifreli arama istiyor. Linphone'da Ayarlar > Güvenlik (veya Aramalar) > "
                   "Medya şifreleme: Yok yapın ve 'Şifreleme zorunlu' seçeneğini kapatın.")
CODEC_HINT = "Telefondaki Linphone'da Ayarlar > Ses > Kodekler kısmından PCMU ve PCMA'yı açın."


def parse_sdp(body: bytes) -> Optional[Tuple[str, int, List[int], str]]:
    """Returns (ip, port, payload types, profile) of the audio stream."""
    text = body.decode("utf-8", "replace")
    ip, port, payloads, profile = None, None, [], ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("c=IN IP4 ") and ip is None:
            ip = line.split()[-1]
        elif line.startswith("m=audio "):
            fields = line.split()
            port = int(fields[1])
            profile = fields[2].upper() if len(fields) > 2 else ""
            payloads = [int(p) for p in fields[3:] if p.isdigit()]
            # a media-level c= line overrides the session one
            ip_media = re.search(r"m=audio[^\n]*\n(?:[^m][^\n]*\n)*?c=IN IP4 (\S+)", text)
            if ip_media:
                ip = ip_media.group(1)
    if ip is None or port is None:
        return None
    return ip, port, payloads, profile


# ---------------------------------------------------------
# RTP
# ---------------------------------------------------------

class RtpSession:
    def __init__(self, bind_ip: str = "0.0.0.0"):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for _ in range(50):
            port = random.randrange(20000, 30000, 2)
            try:
                self.sock.bind((bind_ip, port))
                break
            except OSError:
                continue
        else:
            raise OSError("No free RTP port")
        self.port = self.sock.getsockname()[1]
        self.sock.settimeout(0.5)
        self.remote: Optional[Tuple[str, int]] = None
        self.pt = 0
        self.on_audio: Optional[Callable[[np.ndarray], None]] = None
        self._out = collections.deque()
        self._out_lock = threading.Lock()
        self._running = False
        self._latched = False

    def set_remote(self, ip: str, port: int, pt: int):
        self.remote, self.pt = (ip, port), pt

    def start(self):
        self._running = True
        threading.Thread(target=self._send_loop, daemon=True).start()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def stop(self):
        self._running = False
        try:
            self.sock.close()
        except OSError:
            pass

    def play(self, pcm: np.ndarray):
        pcm = pcm.astype(np.int16)
        with self._out_lock:
            for i in range(0, len(pcm), FRAME):
                frame = pcm[i:i + FRAME]
                if len(frame) < FRAME:
                    frame = np.pad(frame, (0, FRAME - len(frame)))
                self._out.append(frame)

    def clear_playback(self):
        with self._out_lock:
            self._out.clear()

    def is_playing(self) -> bool:
        return bool(self._out)

    def wait_playback(self, timeout: float = 30):
        deadline = time.time() + timeout
        while self._out and time.time() < deadline and self._running:
            time.sleep(0.05)

    def _send_loop(self):
        seq, ts, ssrc = random.randrange(65536), random.randrange(2 ** 32), random.randrange(2 ** 32)
        marker = 0x80
        next_time = time.perf_counter()
        while self._running:
            next_time += 0.02
            delay = next_time - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            elif delay < -0.2:          # fell far behind (e.g. system sleep): resync
                next_time = time.perf_counter()
            with self._out_lock:
                frame = self._out.popleft() if self._out else None
            payload = g711_encode(frame, self.pt) if frame is not None else bytes([_SILENCE[self.pt]]) * FRAME
            if self.remote:
                header = struct.pack("!BBHII", 0x80, marker | self.pt, seq, ts, ssrc)
                try:
                    self.sock.sendto(header + payload, self.remote)
                except OSError:
                    pass
                marker = 0
            seq = (seq + 1) & 0xFFFF
            ts = (ts + FRAME) & 0xFFFFFFFF

    def _recv_loop(self):
        while self._running:
            try:
                data, addr = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            if len(data) < 12 or data[0] >> 6 != 2:
                continue
            cc = data[0] & 0x0F
            offset = 12 + 4 * cc
            if data[0] & 0x10 and len(data) >= offset + 4:     # header extension
                offset += 4 + 4 * struct.unpack("!H", data[offset + 2:offset + 4])[0]
            pt = data[1] & 0x7F
            if pt not in _DECODE or len(data) <= offset:
                continue
            # Symmetric RTP: send back to where the phone's audio really comes from (NAT)
            if not self._latched and self.remote != addr:
                self.remote = addr
            self._latched = True
            if self.on_audio:
                self.on_audio(g711_decode(data[offset:], pt))


# ---------------------------------------------------------
# CALL
# ---------------------------------------------------------

class SipCall:
    def __init__(self, phone: "SipPhone", call_id: str, incoming: bool):
        self.phone = phone
        self.call_id = call_id
        self.incoming = incoming
        self.local_tag = _rand(10)
        self.local_hdr = ""
        self.remote_hdr = ""
        self.remote_target = ""
        self.route_set: List[str] = []
        self.cseq = random.randint(1, 1000)
        self.media = RtpSession()
        self.established = False
        self.ended = threading.Event()
        self.acked = threading.Event()
        self.last_response: Optional[bytes] = None
        self.ack_data: Optional[bytes] = None
        self.invite_data: Optional[bytes] = None
        self.invite_branch = ""
        self.invite_cseq = 0
        self.invite_uri = ""
        self.intro: Optional[str] = None
        self.reject_hint = ""
        self.remote_wants_zrtp = False
        self.started_at = 0.0
        self._utterances: "queue.Queue[np.ndarray]" = queue.Queue()
        # voice activity detection state
        self._noise = 0.005
        self._talking = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._buffer: List[np.ndarray] = []
        self._preroll = collections.deque(maxlen=10)

    # --- SDP -------------------------------------------------------------
    def local_sdp(self) -> bytes:
        ip = self.phone.local_ip
        sess = str(random.randint(10 ** 8, 10 ** 9))
        return (
            "v=0\r\n"
            f"o=jarvis {sess} {sess} IN IP4 {ip}\r\n"
            "s=Jarvis\r\n"
            f"c=IN IP4 {ip}\r\n"
            "t=0 0\r\n"
            f"m=audio {self.media.port} RTP/AVP 0 8 101\r\n"
            "a=rtpmap:0 PCMU/8000\r\n"
            "a=rtpmap:8 PCMA/8000\r\n"
            "a=rtpmap:101 telephone-event/8000\r\n"
            "a=fmtp:101 0-15\r\n"
            "a=ptime:20\r\n"
            "a=sendrecv\r\n"
        ).encode()

    def apply_remote_sdp(self, body: bytes) -> bool:
        sdp = parse_sdp(body) if body else None
        if not sdp:
            return False
        ip, port, payloads, profile = sdp
        text = body.decode("utf-8", "replace")
        self.remote_wants_zrtp = "a=zrtp-hash" in text
        if "SAVP" in profile:                       # SRTP / DTLS only: we only speak plain RTP
            self.reject_hint = ENCRYPTION_HINT
            return False
        codec = next((p for p in payloads if p in (0, 8)), None)
        if codec is None:
            self.reject_hint = CODEC_HINT
            return False
        if ip != "0.0.0.0":
            self.media.set_remote(ip, port, codec)
        return True

    # --- dialog requests ---------------------------------------------------
    def dialog_request(self, method: str, extra: List[Tuple[str, str]] = (), body: bytes = b""):
        self.cseq += 1
        branch = self.phone.new_branch()
        headers = [("Via", self.phone.via(branch)), ("Max-Forwards", "70")]
        headers += [("Route", r) for r in self.route_set]
        headers += [("From", self.local_hdr), ("To", self.remote_hdr), ("Call-ID", self.call_id),
                    ("CSeq", f"{self.cseq} {method}"), ("Contact", self.phone.contact()),
                    ("User-Agent", USER_AGENT)] + list(extra)
        data = build_message(f"{method} {self.remote_target} SIP/2.0", headers, body)
        return self.phone.transact(data, branch, method)

    # --- lifecycle -----------------------------------------------------------
    def hangup(self, send_bye: bool = True):
        if self.ended.is_set():
            return
        self.ended.set()
        if send_bye and self.established:
            threading.Thread(target=self.dialog_request, args=("BYE",), daemon=True).start()
        self.media.stop()
        self.phone.call_finished(self)

    def start_conversation(self):
        self.established = True
        self.started_at = time.time()
        if self.phone.on_call_start:
            self.phone.on_call_start()
        self.media.on_audio = self._on_audio
        self.media.start()
        self.phone.log("sys", "SYS: 📞 Linphone görüşmesi başladı.")
        threading.Thread(target=self._conversation_loop, daemon=True).start()

    def say(self, text: str):
        try:
            pcm = self.phone.tts(text)
        except Exception as e:
            print(f"[SIP] TTS error: {e}")
            return
        self.media.play(pcm)

    def _on_audio(self, pcm: np.ndarray):
        frame = pcm.astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(frame * frame)))
        playing = self.media.is_playing()
        threshold = max(self._noise * 3.0, 0.02) * (1.5 if playing else 1.0)
        if rms > threshold:
            self._speech_frames += 1
            self._silence_frames = 0
            if not self._talking and self._speech_frames >= 3:
                self._talking = True
                self._buffer = list(self._preroll)
            if self._talking:
                self._buffer.append(pcm)
                # Barge-in: sahibi Jarvis konuşurken araya girerse sustur
                if playing and self._speech_frames >= 10:
                    self.media.clear_playback()
            else:
                self._preroll.append(pcm)
        else:
            if self._talking:
                self._silence_frames += 1
                self._buffer.append(pcm)
                if self._silence_frames >= 35:          # 0.7 s sessizlik -> cümle bitti
                    self._finish_utterance()
            else:
                self._speech_frames = 0
                self._noise = 0.95 * self._noise + 0.05 * rms
                self._preroll.append(pcm)
        if self._talking and len(self._buffer) > 750:     # en fazla 15 sn
            self._finish_utterance()

    def _finish_utterance(self):
        if self._speech_frames >= 15:                    # en az 0.3 sn konuşma
            self._utterances.put(np.concatenate(self._buffer))
        self._talking = False
        self._speech_frames = self._silence_frames = 0
        self._buffer = []

    def _conversation_loop(self):
        self.say(self.intro or "Merhaba efendim, Jarvis dinliyor.")
        while not self.ended.is_set():
            try:
                pcm = self._utterances.get(timeout=0.5)
            except queue.Empty:
                continue
            text = (self.phone.stt(pcm) or "").strip()
            if not text or self.ended.is_set():
                continue
            self.phone.log("user", f"📞 USR: {text}")
            if is_hangup(text):
                self.say("Görüşmek üzere efendim.")
                self.media.wait_playback(10)
                self.phone.log("sys", "SYS: 📞 Linphone görüşmesi bitti.")
                self.hangup()
                return
            try:
                answer = self.phone.respond(text) or ""
            except Exception as e:
                print(f"[SIP] AI error: {e}")
                answer = ""
            answer = answer.strip() or "Şu an cevap veremedim, tekrar sorar mısınız?"
            self.phone.log("sys", f"📞 JRV: {answer}")
            self.say(answer)


# ---------------------------------------------------------
# PHONE (registration, signalling)
# ---------------------------------------------------------

class SipPhone:
    def __init__(self, user: str, password: str, owner: str, domain: str = "sip.linphone.org",
                 proxy: Optional[str] = None, local_port: int = 5070,
                 respond: Callable[[str], str] = None, log: Callable[[str, str], None] = None,
                 stt: Callable[[np.ndarray], str] = default_stt, tts: Callable[[str], np.ndarray] = default_tts,
                 on_call_start: Callable[[], None] = None):
        self.user = user
        self.password = password
        self.domain = domain
        self.owner = normalize_address(owner, domain)
        host, _, port = (proxy or domain).partition(":")
        self.server_addr = (socket.gethostbyname(host), int(port or 5060))
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", local_port))
        self.sock.settimeout(0.5)
        self.local_port = self.sock.getsockname()[1]
        self.local_ip = self._local_ip()
        self.contact_host, self.contact_port = self.local_ip, self.local_port
        self.respond = respond or (lambda text: "")
        self.log = log or (lambda sender, text: print(text))
        self.stt, self.tts = stt, tts
        self.on_call_start = on_call_start
        self.registered = False
        self.calls = {}
        self._transactions = {}
        self._lock = threading.Lock()
        self._running = False
        self._reg_call_id = _rand(20)
        self._reg_tag = _rand(10)
        self._reg_cseq = 0
        self._nat_fixed = False
        self.last_error = ""

    @classmethod
    def from_env(cls, **kwargs) -> "SipPhone":
        return cls(user=_env("JARVIS_SIP_USER"), password=_env("JARVIS_SIP_PASSWORD"),
                   owner=_env("JARVIS_SIP_OWNER"), domain=_env("JARVIS_SIP_DOMAIN", "sip.linphone.org"),
                   proxy=_env("JARVIS_SIP_PROXY") or None, local_port=int(_env("JARVIS_SIP_PORT", "5070")),
                   **kwargs)

    def _local_ip(self) -> str:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(self.server_addr)
            return probe.getsockname()[0]
        except OSError:
            return "127.0.0.1"
        finally:
            probe.close()

    # --- helpers -------------------------------------------------------------
    def new_branch(self) -> str:
        return "z9hG4bK" + _rand(16)

    def via(self, branch: str) -> str:
        return f"SIP/2.0/UDP {self.local_ip}:{self.local_port};branch={branch};rport"

    def contact(self) -> str:
        return f"<sip:{self.user}@{self.contact_host}:{self.contact_port};transport=udp>"

    def aor(self) -> str:
        return f"sip:{self.user}@{self.domain}"

    def send(self, data: bytes, addr: Tuple[str, int] = None):
        try:
            self.sock.sendto(data, addr or self.server_addr)
        except OSError as e:
            print(f"[SIP] Send failed: {e}")

    def transact(self, data: bytes, branch: str, method: str, timeout: float = 32.0,
                 on_provisional: Callable[[SipMessage], None] = None) -> Optional[SipMessage]:
        """Sends a request, retransmitting over UDP, and returns the final response (or None)."""
        q: "queue.Queue[SipMessage]" = queue.Queue()
        key = (branch, method)
        with self._lock:
            self._transactions[key] = q
        try:
            deadline = time.time() + timeout
            interval, provisional = T1, False
            self.send(data)
            next_retransmit = time.time() + interval
            while time.time() < deadline:
                try:
                    resp = q.get(timeout=max(0.01, min(next_retransmit, deadline) - time.time()))
                except queue.Empty:
                    if not (provisional and method == "INVITE"):
                        self.send(data)
                    interval = min(interval * 2, T2)
                    next_retransmit = time.time() + interval
                    continue
                if resp.status < 200:
                    provisional = True
                    if on_provisional:
                        on_provisional(resp)
                    continue
                return resp
            return None
        finally:
            with self._lock:
                self._transactions.pop(key, None)

    # --- lifecycle -------------------------------------------------------------
    def start(self):
        self._running = True
        threading.Thread(target=self._recv_loop, daemon=True).start()
        threading.Thread(target=self._register_loop, daemon=True).start()
        threading.Thread(target=self._keepalive_loop, daemon=True).start()

    def stop(self):
        for call in list(self.calls.values()):
            call.hangup()
        if self.registered:
            self.register(expires=0)
        self._running = False

    def _keepalive_loop(self):
        # NAT deliğini açık tutmak için boş satır (RFC 5626 CRLF keep-alive)
        while self._running:
            time.sleep(KEEPALIVE_SECONDS)
            self.send(b"\r\n\r\n")

    def _register_loop(self):
        first = True
        while self._running:
            ok = False
            try:
                ok = self.register()
            except Exception as e:
                self.last_error = str(e)
                print(f"[SIP] Register error: {e}")
            if ok and not self.registered:
                self.log("sys", "SYS: 📞 Linphone hattı hazır. Jarvis'i Linphone'dan arayabilirsiniz.")
            elif not ok and (self.registered or first):
                self.log("err", f"ERR: 📞 Linphone'a bağlanılamadı: {self.last_error} Yeniden deneniyor.")
            first = False
            self.registered = ok
            time.sleep(REGISTER_EXPIRES * 0.8 if ok else 30)

    def register(self, expires: int = REGISTER_EXPIRES) -> bool:
        auth = None
        for _ in range(3):
            self._reg_cseq += 1
            branch = self.new_branch()
            headers = [("Via", self.via(branch)), ("Max-Forwards", "70"),
                       ("From", f"<{self.aor()}>;tag={self._reg_tag}"), ("To", f"<{self.aor()}>"),
                       ("Call-ID", self._reg_call_id), ("CSeq", f"{self._reg_cseq} REGISTER"),
                       ("Contact", f"{self.contact()};expires={expires}"), ("Expires", str(expires)),
                       ("Allow", "INVITE, ACK, CANCEL, BYE, OPTIONS, INFO, UPDATE, NOTIFY, MESSAGE"),
                       ("User-Agent", USER_AGENT)]
            if auth:
                headers.append(auth)
            resp = self.transact(build_message(f"REGISTER sip:{self.domain} SIP/2.0", headers), branch, "REGISTER")
            if resp is None:
                self.last_error = "Linphone sunucusu cevap vermedi (internet bağlantısı veya güvenlik duvarı)."
                print(f"[SIP] No answer from {self.server_addr[0]}:{self.server_addr[1]}")
                return False
            if resp.status in (401, 407):
                if auth:
                    self.last_error = "Kullanıcı adı veya şifre hatalı (JARVIS_SIP_USER / JARVIS_SIP_PASSWORD)."
                    print("[SIP] Linphone rejected the username/password.")
                    return False
                auth = digest_authorization(resp, "REGISTER", f"sip:{self.domain}", self.user, self.password)
                continue
            if 200 <= resp.status < 300:
                params = _via_params(resp.get("via"))
                public = (params.get("received") or self.contact_host,
                          int(params["rport"]) if params.get("rport") else self.contact_port)
                if expires and not self._nat_fixed and public != (self.contact_host, self.contact_port):
                    # Behind NAT: register the public address the server saw, so calls reach us
                    self._nat_fixed = True
                    self.contact_host, self.contact_port = public
                    return self.register(expires)
                return True
            detail = resp.get("warning") or resp.get("reason")
            if resp.status == 403 and auth:
                self.last_error = ("Linphone kullanıcı adını/şifreyi kabul etmedi ya da hesap henüz etkinleştirilmemiş "
                                   "(e-postadaki onay linkine tıklayın).")
            else:
                self.last_error = f"Sunucu kaydı reddetti ({resp.status} {resp.reason})."
            print(f"[SIP] Register failed: {resp.status} {resp.reason} (auth sent: {bool(auth)}) {detail}")
            return False
        return False

    def call_finished(self, call: SipCall):
        with self._lock:
            self.calls.pop(call.call_id, None)

    # --- receiving -------------------------------------------------------------
    def _recv_loop(self):
        while self._running:
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data.strip():
                continue
            try:
                msg = SipMessage(data)
                if msg.is_response:
                    self._on_response(msg)
                else:
                    self._on_request(msg, addr)
            except Exception as e:
                print(f"[SIP] Could not handle message: {e}")

    def _on_response(self, msg: SipMessage):
        num, method = msg.cseq
        with self._lock:
            q = self._transactions.get((msg.branch, method))
        if q:
            q.put(msg)
            return
        # Retransmitted 200 OK for an INVITE we already acknowledged -> resend ACK
        call = self.calls.get(msg.get("call-id"))
        if call and method == "INVITE" and 200 <= msg.status < 300 and call.ack_data:
            self.send(call.ack_data)

    def respond_to(self, req: SipMessage, addr, status: int, reason: str, to_tag: str = "",
                   extra: List[Tuple[str, str]] = (), body: bytes = b"", record_route: bool = False) -> bytes:
        to = req.get("to")
        if to_tag and not tag_of(to):
            to += f";tag={to_tag}"
        headers = [("Via", v) for v in req.get_all("via")]
        headers += [("From", req.get("from")), ("To", to), ("Call-ID", req.get("call-id")), ("CSeq", req.get("cseq"))]
        if record_route:
            headers += [("Record-Route", rr) for rr in req.get_all("record-route")]
        headers += [("User-Agent", USER_AGENT)] + list(extra)
        data = build_message(f"SIP/2.0 {status} {reason}", headers, body)
        self.send(data, addr)
        return data

    def _on_request(self, req: SipMessage, addr):
        method = req.method
        call = self.calls.get(req.get("call-id"))
        if method == "INVITE":
            if call and tag_of(req.get("to")):          # re-INVITE inside the call
                call.apply_remote_sdp(req.body)
                self.respond_to(req, addr, 200, "OK", call.local_tag, body=call.local_sdp(), record_route=True,
                                extra=[("Contact", self.contact()), ("Content-Type", "application/sdp")])
            elif call and call.last_response:           # retransmitted initial INVITE
                self.send(call.last_response, addr)
            elif not call:
                self._incoming_invite(req, addr)
        elif method == "ACK":
            if call:
                call.acked.set()
        elif method == "BYE":
            self.respond_to(req, addr, 200, "OK")
            if call:
                reason = req.get("reason")
                self.log("sys", "SYS: 📞 Linphone görüşmesi bitti." + (f" ({reason})" if reason else ""))
                # Phone hung up right away: almost always its "encryption mandatory" setting (ZRTP)
                if call.started_at and time.time() - call.started_at < 15 and call.remote_wants_zrtp:
                    self.log("err", f"ERR: 📞 {ENCRYPTION_HINT}")
                call.hangup(send_bye=False)
        elif method == "CANCEL":
            self.respond_to(req, addr, 200, "OK")
            if call and not call.established and call.invite_data:
                call.last_response = self.respond_to(SipMessage(call.invite_data), addr, 487, "Request Terminated",
                                                     call.local_tag)
                call.hangup(send_bye=False)
        elif method in ("OPTIONS", "INFO", "NOTIFY", "MESSAGE", "UPDATE", "PRACK"):
            self.respond_to(req, addr, 200, "OK")
        else:
            self.respond_to(req, addr, 501, "Not Implemented")

    def _incoming_invite(self, req: SipMessage, addr):
        caller = normalize_address(uri_of(req.get("from")), self.domain)
        # Sadece Linphone sunucusundan gelen ve sahibin hesabından yapılan aramalar
        from_server = addr[0] == self.server_addr[0] or _env("JARVIS_SIP_ALLOW_DIRECT") == "1"
        if not from_server or caller != self.owner:
            print(f"[SIP] Rejected call from {caller} ({addr[0]})")
            self.respond_to(req, addr, 403, "Forbidden", _rand(8))
            return
        if self.calls:
            self.respond_to(req, addr, 486, "Busy Here", _rand(8))
            return
        call = SipCall(self, req.get("call-id"), incoming=True)
        call.invite_data = req.raw
        call.local_hdr = req.get("to") + f";tag={call.local_tag}"
        call.remote_hdr = req.get("from")
        call.remote_target = uri_of(req.get("contact")) or uri_of(req.get("from"))
        call.route_set = req.get_all("record-route")
        with self._lock:
            self.calls[call.call_id] = call
        if not call.apply_remote_sdp(req.body):
            self.log("err", f"ERR: 📞 Gelen arama açılamadı. {call.reject_hint}")
            call.last_response = self.respond_to(req, addr, 488, "Not Acceptable Here", call.local_tag)
            call.hangup(send_bye=False)
            return
        self.respond_to(req, addr, 100, "Trying")
        call.last_response = self.respond_to(req, addr, 180, "Ringing", call.local_tag, record_route=True,
                                             extra=[("Contact", self.contact())])
        threading.Thread(target=self._answer, args=(call, req, addr), daemon=True).start()

    def _answer(self, call: SipCall, req: SipMessage, addr):
        time.sleep(0.5)
        if call.ended.is_set():
            return
        ok = self.respond_to(req, addr, 200, "OK", call.local_tag, body=call.local_sdp(), record_route=True,
                             extra=[("Contact", self.contact()), ("Content-Type", "application/sdp"),
                                    ("Allow", "INVITE, ACK, CANCEL, BYE, OPTIONS, INFO, UPDATE")])
        call.last_response = ok
        call.start_conversation()
        # 200 OK is retransmitted until the ACK arrives (UDP)
        interval, deadline = T1, time.time() + 32
        while not call.acked.wait(interval) and time.time() < deadline and not call.ended.is_set():
            self.send(ok, addr)
            interval = min(interval * 2, T2)

    # --- calling the owner -----------------------------------------------------
    def call_owner(self, reason: str = "") -> str:
        if not self.registered:
            return "Linphone hattı henüz bağlı değil. İnternet bağlantısını ve Linphone bilgilerini kontrol edin."
        if self.calls:
            return "Zaten bir görüşme var."
        intro = "Merhaba efendim, Jarvis arıyor."
        if reason:
            intro += " " + reason.strip()
        call = SipCall(self, _rand(24), incoming=False)
        call.intro = intro
        with self._lock:
            self.calls[call.call_id] = call
        threading.Thread(target=self._dial, args=(call,), daemon=True).start()
        return "Linphone'dan sizi arıyorum."

    def _dial(self, call: SipCall):
        uri = f"sip:{self.owner}"
        call.local_hdr = f"<{self.aor()}>;tag={call.local_tag}"
        call.remote_hdr = f"<{uri}>"
        call.invite_uri = uri
        auth = None
        answered = threading.Event()
        cancel_timer = threading.Timer(RING_TIMEOUT, lambda: None if answered.is_set() else self._cancel(call))
        cancel_timer.daemon = True
        cancel_timer.start()
        try:
            for _ in range(3):
                call.cseq += 1
                call.invite_cseq = call.cseq
                call.invite_branch = self.new_branch()
                headers = [("Via", self.via(call.invite_branch)), ("Max-Forwards", "70"),
                           ("From", call.local_hdr), ("To", call.remote_hdr), ("Call-ID", call.call_id),
                           ("CSeq", f"{call.cseq} INVITE"), ("Contact", self.contact()),
                           ("Content-Type", "application/sdp"),
                           ("Allow", "INVITE, ACK, CANCEL, BYE, OPTIONS, INFO, UPDATE"),
                           ("User-Agent", USER_AGENT)]
                if auth:
                    headers.append(auth)
                call.invite_data = build_message(f"INVITE {uri} SIP/2.0", headers, call.local_sdp())
                resp = self.transact(call.invite_data, call.invite_branch, "INVITE", timeout=RING_TIMEOUT + 15)
                if resp is None:
                    self.log("err", "ERR: 📞 Linphone araması cevapsız kaldı.")
                    break
                if 200 <= resp.status < 300:
                    answered.set()
                    call.remote_hdr = resp.get("to")
                    call.remote_target = uri_of(resp.get("contact")) or uri
                    call.route_set = list(reversed(resp.get_all("record-route")))
                    call.apply_remote_sdp(resp.body)
                    self._send_ack(call)
                    call.start_conversation()
                    return
                self._ack_failure(call, resp)
                if resp.status in (401, 407) and not auth:
                    auth = digest_authorization(resp, "INVITE", uri, self.user, self.password)
                    continue
                reasons = {486: "meşgul", 480: "şu an ulaşılamıyor (Linphone kapalı olabilir)",
                           603: "aramayı reddetti", 487: "açmadı", 404: "Linphone hesabı bulunamadı",
                           488: f"telefon ses ayarlarını kabul etmedi. {ENCRYPTION_HINT} {CODEC_HINT}"}
                self.log("err", f"ERR: 📞 Linphone araması başarısız: {reasons.get(resp.status, f'{resp.status} {resp.reason}')}")
                break
        finally:
            cancel_timer.cancel()
        call.hangup(send_bye=False)

    def _send_ack(self, call: SipCall):
        branch = self.new_branch()
        headers = [("Via", self.via(branch)), ("Max-Forwards", "70")]
        headers += [("Route", r) for r in call.route_set]
        headers += [("From", call.local_hdr), ("To", call.remote_hdr), ("Call-ID", call.call_id),
                    ("CSeq", f"{call.invite_cseq} ACK"), ("User-Agent", USER_AGENT)]
        call.ack_data = build_message(f"ACK {call.remote_target} SIP/2.0", headers)
        self.send(call.ack_data)

    def _ack_failure(self, call: SipCall, resp: SipMessage):
        """ACK for a non-2xx final response: same branch as the INVITE (RFC 3261 17.1.1.3)."""
        headers = [("Via", self.via(call.invite_branch)), ("Max-Forwards", "70"),
                   ("From", call.local_hdr), ("To", resp.get("to")), ("Call-ID", call.call_id),
                   ("CSeq", f"{call.invite_cseq} ACK"), ("User-Agent", USER_AGENT)]
        self.send(build_message(f"ACK {call.invite_uri} SIP/2.0", headers))

    def _cancel(self, call: SipCall):
        if call.established or call.ended.is_set() or not call.invite_branch:
            return
        headers = [("Via", self.via(call.invite_branch)), ("Max-Forwards", "70"),
                   ("From", call.local_hdr), ("To", call.remote_hdr), ("Call-ID", call.call_id),
                   ("CSeq", f"{call.invite_cseq} CANCEL"), ("User-Agent", USER_AGENT)]
        self.transact(build_message(f"CANCEL {call.invite_uri} SIP/2.0", headers), call.invite_branch, "CANCEL")
