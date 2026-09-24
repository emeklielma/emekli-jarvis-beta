import asyncio
import edge_tts
import ctypes
import os
import speech_recognition as sr
import sounddevice as sd
import soundfile as sf
import numpy as np
import queue
import time
from core.state import state

# TTS voices: British male for English (Jarvis-like), Turkish male for Turkish text.
# JARVIS_TTS_VOICE forces a single voice for everything.
EN_VOICE = 'en-GB-RyanNeural'
TR_VOICE = 'tr-TR-AhmetNeural'
_TR_CHARS = set('çğıöşüÇĞİÖŞÜ')
_TR_WORDS = {'ve', 'bir', 'bu', 'için', 'efendim', 'tamam', 'açıyorum', 'değil', 'evet', 'hayır', 'ne', 'nasıl'}

def pick_voice(text: str) -> str:
    forced = os.getenv("JARVIS_TTS_VOICE")
    if forced:
        return forced
    words = {w.strip('.,!?;:').lower() for w in text.split()}
    if any(c in _TR_CHARS for c in text) or words & _TR_WORDS:
        return TR_VOICE
    return EN_VOICE

# Async Queue for sentences to be spoken
_speech_queue = asyncio.Queue()

async def speak_sentence_worker():
    """Background worker that pulls sentences from the queue and speaks them instantly."""
    while True:
        try:
            text = await _speech_queue.get()
            if not text.strip():
                _speech_queue.task_done()
                continue
            voice = pick_voice(text)
            temp_audio = f"jarvis_response_{int(time.time()*1000)}.mp3"
            
            try:
                # Generate audio
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(temp_audio)
                
                # Play audio using MCI in a background thread so it doesn't block the loop
                def play_audio():
                    mci = ctypes.windll.winmm.mciSendStringW
                    alias = f"media_{int(time.time()*1000)}"
                    mci(f'open "{temp_audio}" alias {alias}', None, 0, None)
                    mci(f'play {alias} wait', None, 0, None)
                    mci(f'close {alias}', None, 0, None)
                    if os.path.exists(temp_audio):
                        try:
                            os.remove(temp_audio)
                        except:
                            pass

                # Store the playback task in state so it can be cancelled
                task = asyncio.create_task(asyncio.to_thread(play_audio))
                state.register_task("audio_playback_task", task)
                state.is_speaking = True
                try:
                    await task
                finally:
                    state.is_speaking = False
                
            except asyncio.CancelledError:
                # If interrupted, stop playback
                pass
            except Exception as e:
                print(f"TTS Error: {e}")
            finally:
                _speech_queue.task_done()
                if os.path.exists(temp_audio):
                    try:
                        os.remove(temp_audio)
                    except:
                        pass
        except asyncio.CancelledError:
            break

def clear_speech_queue():
    """Clears the speech queue upon barge-in."""
    while not _speech_queue.empty():
        try:
            _speech_queue.get_nowait()
            _speech_queue.task_done()
        except:
            break

async def enqueue_sentence(text: str):
    await _speech_queue.put(text)

class SentenceBuffer:
    def __init__(self):
        self.buffer = ""
        self.delimiters = {'.', '!', '?', '\n'}
        
    async def add_token(self, token: str):
        self.buffer += token
        # Check if buffer ends with a sentence delimiter
        if any(self.buffer.endswith(d) for d in self.delimiters) or any(self.buffer.endswith(d + " ") for d in self.delimiters):
            sentence = self.buffer.strip()
            if sentence:
                await enqueue_sentence(sentence)
            self.buffer = ""
            
    async def flush(self):
        sentence = self.buffer.strip()
        if sentence:
            await enqueue_sentence(sentence)
        self.buffer = ""

# ---------------------------------------------------------
# MICROPHONE / SPEECH-TO-TEXT
# ---------------------------------------------------------
# Tanıma dili: kullanıcı Jarvis'e Türkçe konuşuyor, bu yüzden varsayılan tr-TR.
# İngilizce konuşmak için .env içine JARVIS_STT_LANG=en-US yazılabilir.
STT_LANGUAGE = os.getenv("JARVIS_STT_LANG", "tr-TR")
# Belirli bir mikrofonu seçmek için cihaz numarası veya isminin bir parçası
# (örn. JARVIS_MIC_DEVICE=2 veya JARVIS_MIC_DEVICE=Headset). Boşsa varsayılan mikrofon.
MIC_DEVICE = os.getenv("JARVIS_MIC_DEVICE", "").strip() or None

CHUNK_SECONDS = 0.25
PRE_ROLL_CHUNKS = 2        # konuşma başlamadan önceki ~0.5 sn de kayda eklenir (ilk hece kesilmesin)
END_SILENCE_CHUNKS = 3     # ~0.75 sn sessizlik = cümle bitti
MAX_RECORD_CHUNKS = 60     # en fazla ~15 sn kayıt
MIN_THRESHOLD = 0.004
MAX_THRESHOLD = 0.06

# Ortam gürültüsü seviyesi; her dinlemede yeniden 0.5 sn kalibrasyon yapmak yerine
# bir kez ölçülüp sessiz anlarda yavaşça güncelleniyor. Eskiden her listen() çağrısında
# kalibrasyon yapılıyordu; kullanıcı o sırada konuşmaya başlarsa eşik çok yükselip
# Jarvis hiç "duymuyordu".
_noise_floor = None
_mic_logged = False


def _resolve_input_device():
    if MIC_DEVICE is None:
        return None
    return int(MIC_DEVICE) if MIC_DEVICE.isdigit() else MIC_DEVICE


def _rms(chunk):
    return float(np.sqrt(np.mean(np.square(chunk))))


def _threshold():
    base = max((_noise_floor or 0.0) * 3.0, MIN_THRESHOLD)
    # Jarvis hoparlörden konuşurken mikrofon kendi sesini duymasın diye eşik yükseltilir;
    # yüksek sesle araya girmek (barge-in) yine mümkün.
    if state.is_speaking:
        base *= 3.0
    return min(base, MAX_THRESHOLD)


def record_audio(filename="temp.wav", on_speech_start=None):
    global _noise_floor, _mic_logged
    try:
        device = _resolve_input_device()
        device_info = sd.query_devices(device, 'input')
        samplerate = int(device_info['default_samplerate'])
        if not _mic_logged:
            print(f"[MIC] Kullanılan mikrofon: {device_info['name']} ({samplerate} Hz), tanıma dili: {STT_LANGUAGE}")
            _mic_logged = True

        q = queue.Queue()
        def callback(indata, frames, time_info, status):
            q.put(indata.copy())

        blocksize = int(samplerate * CHUNK_SECONDS)
        pre_roll = []
        recorded_chunks = []
        silent_chunks = 0
        started_talking = False

        # Mono kayıt: bazı mikrofonlar çok kanal bildiriyor, sessiz kanallar
        # ortalamayı düşürüp konuşmanın algılanmasını engelliyordu.
        with sd.InputStream(device=device, samplerate=samplerate, channels=1, dtype='float32',
                            blocksize=blocksize, callback=callback):
            if _noise_floor is None:
                calib = [q.get() for _ in range(2)]
                _noise_floor = _rms(np.concatenate(calib, axis=0))
                print(f"[MIC] Ortam gürültüsü: {_noise_floor:.4f}, konuşma eşiği: {_threshold():.4f}")

            while state.mic_active:
                try:
                    mydata = q.get(timeout=1.0)
                except queue.Empty:
                    continue
                volume = _rms(mydata)

                if volume > _threshold():
                    if not started_talking:
                        if on_speech_start:
                            on_speech_start()
                        # Barge-in: User started talking, cancel any ongoing AI generation and speech!
                        state.cancel_all_barge_in_tasks()
                        clear_speech_queue()
                        recorded_chunks.extend(pre_roll)
                    started_talking = True
                    silent_chunks = 0
                else:
                    if started_talking:
                        silent_chunks += 1
                    elif not state.is_speaking:
                        # Sessiz anlarda gürültü seviyesini yavaşça takip et
                        _noise_floor = 0.95 * _noise_floor + 0.05 * volume

                if started_talking:
                    recorded_chunks.append(mydata)
                    if silent_chunks >= END_SILENCE_CHUNKS or len(recorded_chunks) > MAX_RECORD_CHUNKS:
                        break
                else:
                    pre_roll.append(mydata)
                    if len(pre_roll) > PRE_ROLL_CHUNKS:
                        pre_roll.pop(0)

        if not recorded_chunks:
            return None

        full_audio = np.concatenate(recorded_chunks, axis=0)
        sf.write(filename, full_audio, samplerate)
        return filename
    except Exception as e:
        print(f"[MIC ERROR] Mikrofon açılamadı: {e}")
        print("[MIC] Mevcut giriş cihazları:")
        try:
            for i, d in enumerate(sd.query_devices()):
                if d['max_input_channels'] > 0:
                    print(f"    {i}: {d['name']}")
        except Exception:
            pass
        raise MicrophoneError(str(e)) from e


class MicrophoneError(Exception):
    pass


def listen(on_speech_start=None):
    """Returns recognized text, "" if speech was not understood, or None if nothing was recorded.
    Raises MicrophoneError if the microphone cannot be opened."""
    audio_file = record_audio(on_speech_start=on_speech_start)
    if not audio_file: return None

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language=STT_LANGUAGE)
            return text.lower()
    except sr.UnknownValueError:
        print("[MIC] Ses algılandı ama anlaşılamadı.")
    except Exception as e:
        print(f"Speech recognition error: {e}")
    finally:
        if os.path.exists(audio_file):
            try:
                os.remove(audio_file)
            except:
                pass
    return ""
