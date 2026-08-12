import asyncio
import edge_tts
import ctypes
import os
import speech_recognition as sr
import sounddevice as sd
import soundfile as sf
import time

def speak(text):
    """Converts text to speech using a realistic voice and plays it."""
    # We only print Jarvis' response from main.py now to avoid duplicates
    try:
        # Use an incredible British male voice similar to Paul Bettany's Jarvis
        voice = 'en-GB-RyanNeural'
        temp_audio = "jarvis_response.mp3"
        
        # Generate the audio
        asyncio.run(edge_tts.Communicate(text, voice).save(temp_audio))
        
        # Play the audio silently in the background using Windows MCI
        mci = ctypes.windll.winmm.mciSendStringW
        mci(f'open "{temp_audio}" alias media', None, 0, None)
        mci('play media wait', None, 0, None)
        mci('close media', None, 0, None)
        
        # Cleanup
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
    except Exception as e:
        print(f"Error speaking: {e}")

import numpy as np

import queue

def record_audio(filename="temp.wav", on_speech_start=None):
    """Records audio dynamically! Stops automatically when you finish speaking."""
    try:
        # Ask Windows what settings the default microphone wants
        device_info = sd.query_devices(sd.default.device[0], 'input')
        samplerate = int(device_info['default_samplerate'])
        channels = device_info['max_input_channels']
        
        # Self-calibrate: Record 0.5s of background noise to find the perfect threshold!
        print("Calibrating microphone...")
        calibration_data = sd.rec(int(samplerate * 0.5), samplerate=samplerate, channels=channels, dtype='float32')
        sd.wait()
        noise_floor = np.abs(calibration_data).mean()
        
        # Set threshold to 5x the background noise (with a minimum baseline)
        silence_threshold = max(noise_floor * 5, 0.001)
        
        q = queue.Queue()
        def callback(indata, frames, time, status):
            q.put(indata.copy())
            
        recorded_chunks = []
        silent_chunks = 0
        started_talking = False
        
        print("Listening... (Speak whenever you're ready)")
        
        # Stream continuously with 0.25 second chunks (gapless!)
        blocksize = int(samplerate * 0.25)
        
        with sd.InputStream(samplerate=samplerate, channels=channels, dtype='float32', blocksize=blocksize, callback=callback):
            while True:
                mydata = q.get()
                volume = np.abs(mydata).mean()
                
                # Print a tiny visual indicator so the user knows he hears them
                if volume > silence_threshold:
                    if not started_talking:
                        print(">>> Hearing you...", end='\r', flush=True)
                        if on_speech_start:
                            on_speech_start()
                    started_talking = True
                    silent_chunks = 0
                else:
                    if started_talking:
                        silent_chunks += 1
                
                # Keep a small buffer before they started talking, then keep everything after
                if started_talking or len(recorded_chunks) < 4:
                    recorded_chunks.append(mydata)
                    
                # If silent for 0.75 seconds (3 chunks) after speaking, stop immediately!
                if started_talking and silent_chunks >= 3:
                    # print("\\nProcessing speech...")
                    break
                    
                # Safety timeout (20 seconds max)
                if len(recorded_chunks) > 80:
                    # print("\\nProcessing speech...")
                    break
                    
        full_audio = np.concatenate(recorded_chunks, axis=0)
        sf.write(filename, full_audio, samplerate)
        return filename
    except Exception as e:
        print(f"Error recording audio: {e}")
        return None

def listen(on_speech_start=None):
    """Records audio dynamically and returns the transcribed text."""
    audio_file = record_audio(on_speech_start=on_speech_start)
    if not audio_file:
        return None  # Hardware failure!
    
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file) as source:
            print("Processing speech...")
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="en-US")
            print(f"You said: {text}")
            return text.lower()
    except sr.UnknownValueError:
        # User was just quiet, don't print anything to avoid spam
        pass
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
    except Exception as e:
        print(f"Speech recognition error: {e}")
    finally:
        # Clean up temporary audio file
        if os.path.exists(audio_file):
            os.remove(audio_file)
            
    return ""
