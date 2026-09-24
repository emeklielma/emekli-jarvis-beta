"""
Mikrofon teşhis aracı: Jarvis seni duymuyorsa bunu çalıştır.

    python mic_test.py          -> varsayılan mikrofonla test
    python mic_test.py 2        -> 2 numaralı mikrofonla test

Mikrofonları listeler, 5 saniye kayıt alıp ses seviyesini gösterir ve
Google ile Türkçe olarak yazıya çevirmeyi dener.
"""

import os
import sys
import time

import numpy as np
import sounddevice as sd
import soundfile as sf
import speech_recognition as sr
from dotenv import load_dotenv

load_dotenv()

device = sys.argv[1] if len(sys.argv) > 1 else (os.getenv("JARVIS_MIC_DEVICE") or None)
if device is not None and str(device).isdigit():
    device = int(device)
lang = os.getenv("JARVIS_STT_LANG", "tr-TR")

print("=== MİKROFONLAR ===")
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        default = " <- varsayılan" if i == sd.default.device[0] else ""
        print(f"  {i}: {d['name']}{default}")

try:
    info = sd.query_devices(device, "input")
except Exception as e:
    print(f"\n[HATA] Mikrofon bulunamadı: {e}")
    print("Windows Ayarlar > Gizlilik > Mikrofon kısmından masaüstü uygulamalarına izin verin.")
    sys.exit(1)

rate = int(info["default_samplerate"])
print(f"\nTest edilen: {info['name']} ({rate} Hz), dil: {lang}")

print("\n1) 1 saniye SESSİZ kalın (ortam gürültüsü ölçülüyor)...")
time.sleep(0.5)
noise = sd.rec(int(rate * 1.0), samplerate=rate, channels=1, dtype="float32", device=device)
sd.wait()
noise_rms = float(np.sqrt(np.mean(np.square(noise))))

print("2) Şimdi 4 saniye KONUŞUN (ör. 'Jarvis saat kaç')...")
speech = sd.rec(int(rate * 4.0), samplerate=rate, channels=1, dtype="float32", device=device)
for i in range(4, 0, -1):
    print(f"   {i}...")
    time.sleep(1)
sd.wait()

chunk = int(rate * 0.25)
levels = [float(np.sqrt(np.mean(np.square(speech[i:i + chunk])))) for i in range(0, len(speech) - chunk + 1, chunk)]
peak = max(levels) if levels else 0.0
threshold = min(max(noise_rms * 3.0, 0.004), 0.06)

print(f"\nOrtam gürültüsü : {noise_rms:.4f}")
print(f"Konuşma eşiği   : {threshold:.4f}  (Jarvis bunun üstünü konuşma sayar)")
print(f"Konuşma zirvesi : {peak:.4f}")
print("Seviye grafiği  : " + "".join("#" if lv > threshold else "." for lv in levels))

if noise_rms < 1e-5 and peak < 1e-5:
    print("\n[SORUN] Mikrofondan hiç ses gelmiyor (tamamen sıfır).")
    print("  - Mikrofon Windows'ta kapalı/sessize alınmış olabilir, ya da izin verilmemiş.")
    print("  - Yanlış cihaz seçili olabilir: yukarıdaki listeden doğru numarayla deneyin: python mic_test.py <numara>")
    sys.exit(1)
if peak <= threshold:
    print("\n[SORUN] Sesiniz eşiğin altında kaldı; Jarvis konuştuğunuzu anlamıyor.")
    print("  - Windows ses ayarlarından mikrofon seviyesini (Giriş ses düzeyi) yükseltin.")
    print("  - Ya da başka bir mikrofon deneyin: python mic_test.py <numara>")
    sys.exit(1)

print("\nSes geliyor. Google'a gönderiliyor...")
sf.write("mic_test.wav", speech, rate)
recognizer = sr.Recognizer()
try:
    with sr.AudioFile("mic_test.wav") as source:
        text = recognizer.recognize_google(recognizer.record(source), language=lang)
    print(f"\n[TAMAM] Anlaşılan: \"{text}\"")
    if device is not None:
        print(f"Jarvis'in bu mikrofonu kullanması için .env dosyasına ekleyin:  JARVIS_MIC_DEVICE={device}")
except sr.UnknownValueError:
    print("\n[SORUN] Ses geldi ama Google anlayamadı. Daha yakından ve net konuşup tekrar deneyin.")
except sr.RequestError as e:
    print(f"\n[SORUN] Google'a ulaşılamadı (internet bağlantısı?): {e}")
finally:
    try:
        os.remove("mic_test.wav")
    except OSError:
        pass
