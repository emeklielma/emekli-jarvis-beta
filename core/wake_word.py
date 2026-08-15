import time
import asyncio
import numpy as np
import sounddevice as sd
import openwakeword
from openwakeword.model import Model
from core.state import state

# Pre-download default models if needed
openwakeword.utils.download_models()

def start_wake_word_thread(main_loop, broadcast_func):
    """
    Runs openwakeword using sounddevice in a blocking loop.
    Calls broadcast_func securely using run_coroutine_threadsafe on main_loop.
    """
    try:
        # Load the default pre-trained 'hey jarvis' model (or alexa if jarvis is unavailable, but openwakeword has 'hey_jarvis' out of the box)
        try:
            oww_model = Model(wakeword_models=['hey_jarvis_v0.1'])
        except Exception:
            oww_model = Model(wakeword_models=['alexa'])
            
        FORMAT = 'int16'
        CHANNELS = 1
        RATE = 16000
        CHUNK = 1280
        
        def callback(indata, frames, time_info, status):
            if not state.mic_active:
                return
            
            audio_data = indata.flatten().astype(np.int16)
            prediction = oww_model.predict(audio_data)
            
            for mdl in oww_model.prediction_buffer.keys():
                score = oww_model.prediction_buffer[mdl][-1]
                if score > 0.5:
                    # Wake word detected!
                    print(f"[WAKE WORD] Detected: {mdl} (Score: {score})")
                    
                    # Prevent multiple triggers
                    state.cancel_all_barge_in_tasks()
                    
                    if main_loop and main_loop.is_running():
                        # Tell UI we are listening
                        asyncio.run_coroutine_threadsafe(
                            broadcast_func({"type": "status", "value": "LISTENING"}), 
                            main_loop
                        )
                        
                        # Clear prediction buffer to avoid rapid re-triggering
                        oww_model.reset()

        with sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype=FORMAT, blocksize=CHUNK, callback=callback):
            while True:
                time.sleep(0.1)

    except Exception as e:
        print(f"[WAKE WORD ERROR] {e}")
