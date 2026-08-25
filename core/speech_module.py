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
            # English voice
            voice = 'en-US-ChristopherNeural'
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
                await task
                
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

def record_audio(filename="temp.wav", on_speech_start=None):
    try:
        device_info = sd.query_devices(sd.default.device[0], 'input')
        samplerate = int(device_info['default_samplerate'])
        channels = device_info['max_input_channels']
        
        calibration_data = sd.rec(int(samplerate * 0.5), samplerate=samplerate, channels=channels, dtype='float32')
        sd.wait()
        noise_floor = np.abs(calibration_data).mean()
        silence_threshold = max(noise_floor * 5, 0.001)
        
        q = queue.Queue()
        def callback(indata, frames, time, status):
            q.put(indata.copy())
            
        recorded_chunks = []
        silent_chunks = 0
        started_talking = False
        
        blocksize = int(samplerate * 0.25)
        
        with sd.InputStream(samplerate=samplerate, channels=channels, dtype='float32', blocksize=blocksize, callback=callback):
            while state.mic_active:
                mydata = q.get()
                volume = np.abs(mydata).mean()
                
                if volume > silence_threshold:
                    if not started_talking:
                        if on_speech_start:
                            on_speech_start()
                        # Barge-in: User started talking, cancel any ongoing AI generation and speech!
                        state.cancel_all_barge_in_tasks()
                        clear_speech_queue()
                    started_talking = True
                    silent_chunks = 0
                else:
                    if started_talking:
                        silent_chunks += 1
                
                if started_talking or len(recorded_chunks) < 4:
                    recorded_chunks.append(mydata)
                    
                if started_talking and silent_chunks >= 2:
                    break
                    
                if len(recorded_chunks) > 80:
                    break
                    
        if not recorded_chunks:
            return None
            
        full_audio = np.concatenate(recorded_chunks, axis=0)
        sf.write(filename, full_audio, samplerate)
        return filename
    except Exception as e:
        print(f"Error recording audio: {e}")
        return None

def listen(on_speech_start=None):
    audio_file = record_audio(on_speech_start=on_speech_start)
    if not audio_file: return None
    
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="en-US")
            return text.lower()
    except sr.UnknownValueError:
        pass
    except Exception as e:
        print(f"Speech recognition error: {e}")
    finally:
        if os.path.exists(audio_file):
            try:
                os.remove(audio_file)
            except:
                pass
    return ""
