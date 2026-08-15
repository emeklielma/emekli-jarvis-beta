"""
J.A.R.V.I.S. Core Application Launcher Engine
Multi-tier, zero-failure Windows application resolver and executor.
Fully supports Turkish & English commands, suffixes, UWP/Store apps, Steam games, and system tools.
"""

import os
import sys
import re
import json
import glob
import time
import shutil
import ctypes
import difflib
import subprocess
from typing import Optional, Dict, List, Tuple, Any

# Path to apps cache file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APPS_CACHE_FILE = os.path.join(BASE_DIR, "apps.json")

# In-memory apps registry
_APPS_INDEX: List[Dict[str, str]] = []
_INDEX_LOADED = False

# ---------------------------------------------------------
# TURKISH & ENGLISH TEXT NORMALIZATION
# ---------------------------------------------------------

TR_CHAR_MAP = {
    'ı': 'i', 'İ': 'i', 'I': 'i',
    'ğ': 'g', 'Ğ': 'g',
    'ü': 'u', 'Ü': 'u',
    'ş': 's', 'Ş': 's',
    'ö': 'o', 'Ö': 'o',
    'ç': 'c', 'Ç': 'c',
    'â': 'a', 'î': 'i', 'û': 'u'
}

# Conversational noise / verbs / polite words to strip out
NOISE_WORDS = {
    'lutfen', 'ac', 'acarmisin', 'acabilir', 'acabilir misin', 'aciver', 'baslat', 'calistir', 
    'goster', 'getir', 'ver', 'uygulamasi', 'uygulamasini', 'uygulamayi', 'uygulamalar', 'uygulamalari',
    'programi', 'programini', 'program', 'programlar', 'programlari', 
    'oyun', 'oyunu', 'oyununu', 'oyunlar', 'oyunlari',
    'penceresi', 'penceresini', 'sekmesi', 'sekmesini',
    'open', 'launch', 'start', 'run', 'show', 'bring', 'please', 'app', 'application', 'game'
}

def clean_word_stem(word: str) -> str:
    """Cleans apostrophes and Turkish inflectional suffixes safely."""
    # 1. Clean apostrophes (e.g. spotify'ı -> spotify, chrome'u -> chrome, steam'e -> steam)
    word = re.sub(r"'[a-z0-9]+$", "", word, flags=re.IGNORECASE)
    
    # 2. Attached Turkish accusative/dative suffixes for longer words
    if len(word) > 5:
        # e.g. defterini -> defteri / defter
        word = re.sub(r"(lerini|larini)$", "", word)
        word = re.sub(r"(sini|sini|sunu|sunu)$", "si", word)
        word = re.sub(r"(ini|ini|unu|unu)$", "i", word)
        word = re.sub(r"(yi|yi|yu|yu)$", "", word)
        word = re.sub(r"(yi|yi)$", "", word)
        
    return word

def normalize_text(text: str, apply_stemming: bool = True) -> str:
    """Normalizes input text by lowercasing, replacing Turkish chars, and cleaning noise words."""
    if not text:
        return ""
    
    text = text.lower().strip()
    
    # 1. Replace Turkish specific characters
    for k, v in TR_CHAR_MAP.items():
        text = text.replace(k, v)
        
    # 2. Split words and clean punctuation
    raw_words = [re.sub(r"[^\w\s']", "", w) for w in text.split()]
    raw_words = [w for w in raw_words if w]
    
    # 3. Filter out noise words
    filtered_words = []
    for w in raw_words:
        # Clean apostrophe first
        base_w = re.sub(r"'[a-z0-9]+$", "", w, flags=re.IGNORECASE)
        if base_w in NOISE_WORDS or w in NOISE_WORDS:
            continue
        if apply_stemming:
            cleaned_w = clean_word_stem(w)
            if cleaned_w in NOISE_WORDS:
                continue
            filtered_words.append(cleaned_w)
        else:
            filtered_words.append(base_w)
            
    if not filtered_words:
        return " ".join([re.sub(r"'[a-z0-9]+$", "", w) for w in raw_words])
        
    return " ".join(filtered_words)

# ---------------------------------------------------------
# CURATED SYSTEM & APPLICATION ALIASES
# ---------------------------------------------------------

SYSTEM_ALIASES: Dict[str, Dict[str, Any]] = {
    # Calculator
    "hesap makinesi": {"target": "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", "fallback": "calc.exe", "name": "Hesap Makinesi", "process": "CalculatorApp.exe"},
    "hesap makinasi": {"target": "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", "fallback": "calc.exe", "name": "Hesap Makinesi", "process": "CalculatorApp.exe"},
    "hesap makine": {"target": "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", "fallback": "calc.exe", "name": "Hesap Makinesi", "process": "CalculatorApp.exe"},
    "hesap makines": {"target": "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", "fallback": "calc.exe", "name": "Hesap Makinesi", "process": "CalculatorApp.exe"},
    "calculator": {"target": "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", "fallback": "calc.exe", "name": "Calculator", "process": "CalculatorApp.exe"},
    "calc": {"target": "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", "fallback": "calc.exe", "name": "Calculator", "process": "CalculatorApp.exe"},

    # Notepad
    "not defteri": {"target": "shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", "fallback": "notepad.exe", "name": "Not Defteri", "process": "Notepad.exe"},
    "not defter": {"target": "shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", "fallback": "notepad.exe", "name": "Not Defteri", "process": "Notepad.exe"},
    "not defteri i": {"target": "shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", "fallback": "notepad.exe", "name": "Not Defteri", "process": "Notepad.exe"},
    "notepad": {"target": "shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", "fallback": "notepad.exe", "name": "Notepad", "process": "Notepad.exe"},
    "notlar": {"target": "shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", "fallback": "notepad.exe", "name": "Not Defteri", "process": "Notepad.exe"},

    # Settings
    "ayarlar": {"target": "ms-settings:", "fallback": "shell:AppsFolder\\windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel", "name": "Windows Ayarlar", "process": "SystemSettings.exe"},
    "ayarlari": {"target": "ms-settings:", "fallback": "shell:AppsFolder\\windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel", "name": "Windows Ayarlar", "process": "SystemSettings.exe"},
    "ayar": {"target": "ms-settings:", "fallback": "shell:AppsFolder\\windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel", "name": "Windows Ayarlar", "process": "SystemSettings.exe"},
    "sistem ayarlari": {"target": "ms-settings:", "fallback": "shell:AppsFolder\\windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel", "name": "Windows Ayarlar", "process": "SystemSettings.exe"},
    "settings": {"target": "ms-settings:", "fallback": "shell:AppsFolder\\windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel", "name": "Settings", "process": "SystemSettings.exe"},

    # Task Manager
    "gorev yoneticisi": {"target": "taskmgr.exe", "fallback": "shell:AppsFolder\\Microsoft.Windows.TaskManager", "name": "Görev Yöneticisi", "process": "Taskmgr.exe"},
    "gorev yoneticis": {"target": "taskmgr.exe", "fallback": "shell:AppsFolder\\Microsoft.Windows.TaskManager", "name": "Görev Yöneticisi", "process": "Taskmgr.exe"},
    "gorev yonetici": {"target": "taskmgr.exe", "fallback": "shell:AppsFolder\\Microsoft.Windows.TaskManager", "name": "Görev Yöneticisi", "process": "Taskmgr.exe"},
    "task manager": {"target": "taskmgr.exe", "fallback": "shell:AppsFolder\\Microsoft.Windows.TaskManager", "name": "Task Manager", "process": "Taskmgr.exe"},
    "taskmgr": {"target": "taskmgr.exe", "fallback": "shell:AppsFolder\\Microsoft.Windows.TaskManager", "name": "Task Manager", "process": "Taskmgr.exe"},

    # File Explorer
    "dosya gezgini": {"target": "explorer.exe", "fallback": "shell:AppsFolder\\Microsoft.Windows.Explorer", "name": "Dosya Gezgini", "process": "explorer.exe"},
    "dosya gezgin": {"target": "explorer.exe", "fallback": "shell:AppsFolder\\Microsoft.Windows.Explorer", "name": "Dosya Gezgini", "process": "explorer.exe"},
    "dosyalar": {"target": "explorer.exe", "fallback": "shell:AppsFolder\\Microsoft.Windows.Explorer", "name": "Dosya Gezgini", "process": "explorer.exe"},
    "file explorer": {"target": "explorer.exe", "fallback": "shell:AppsFolder\\Microsoft.Windows.Explorer", "name": "File Explorer", "process": "explorer.exe"},
    "explorer": {"target": "explorer.exe", "fallback": "shell:AppsFolder\\Microsoft.Windows.Explorer", "name": "File Explorer", "process": "explorer.exe"},
    "bu bilgisayar": {"target": "explorer.exe shell:MyComputerFolder", "fallback": "explorer.exe", "name": "Bu Bilgisayar", "process": "explorer.exe"},
    "bilgisayarim": {"target": "explorer.exe shell:MyComputerFolder", "fallback": "explorer.exe", "name": "Bu Bilgisayar", "process": "explorer.exe"},

    # Control Panel
    "denetim masasi": {"target": "control.exe", "fallback": None, "name": "Denetim Masası", "process": "control.exe"},
    "denetim masa": {"target": "control.exe", "fallback": None, "name": "Denetim Masası", "process": "control.exe"},
    "control panel": {"target": "control.exe", "fallback": None, "name": "Control Panel", "process": "control.exe"},

    # Paint
    "paint": {"target": "shell:AppsFolder\\Microsoft.Paint_8wekyb3d8bbwe!App", "fallback": "mspaint.exe", "name": "Paint", "process": "mspaint.exe"},
    "boya": {"target": "shell:AppsFolder\\Microsoft.Paint_8wekyb3d8bbwe!App", "fallback": "mspaint.exe", "name": "Paint", "process": "mspaint.exe"},
    "mspaint": {"target": "shell:AppsFolder\\Microsoft.Paint_8wekyb3d8bbwe!App", "fallback": "mspaint.exe", "name": "Paint", "process": "mspaint.exe"},
    "paint 3d": {"target": "shell:AppsFolder\\Microsoft.MSPaint_8wekyb3d8bbwe!Microsoft.MSPaint", "fallback": "PaintStudio.View.exe", "name": "Paint 3D", "process": "PaintStudio.View.exe"},

    # Terminal / CMD / PowerShell
    "terminal": {"target": "shell:AppsFolder\\Microsoft.WindowsTerminal_8wekyb3d8bbwe!App", "fallback": "wt.exe", "name": "Terminal", "process": "WindowsTerminal.exe"},
    "windows terminal": {"target": "shell:AppsFolder\\Microsoft.WindowsTerminal_8wekyb3d8bbwe!App", "fallback": "wt.exe", "name": "Windows Terminal", "process": "WindowsTerminal.exe"},
    "komut istemi": {"target": "cmd.exe", "fallback": None, "name": "Komut İstemi (CMD)", "process": "cmd.exe"},
    "cmd": {"target": "cmd.exe", "fallback": None, "name": "Command Prompt", "process": "cmd.exe"},
    "powershell": {"target": "powershell.exe", "fallback": "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe", "name": "PowerShell", "process": "powershell.exe"},

    # Camera & Clock & Recorder & Snipping
    "kamera": {"target": "microsoft.windows.camera:", "fallback": "shell:AppsFolder\\Microsoft.WindowsCamera_8wekyb3d8bbwe!App", "name": "Kamera", "process": "WindowsCamera.exe"},
    "camera": {"target": "microsoft.windows.camera:", "fallback": "shell:AppsFolder\\Microsoft.WindowsCamera_8wekyb3d8bbwe!App", "name": "Camera", "process": "WindowsCamera.exe"},
    "saat": {"target": "ms-clock:", "fallback": "shell:AppsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App", "name": "Saat ve Alarm", "process": "Time.exe"},
    "alarm": {"target": "ms-clock:", "fallback": "shell:AppsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App", "name": "Saat ve Alarm", "process": "Time.exe"},
    "clock": {"target": "ms-clock:", "fallback": "shell:AppsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App", "name": "Clock", "process": "Time.exe"},
    "ses kaydedici": {"target": "shell:AppsFolder\\Microsoft.WindowsSoundRecorder_8wekyb3d8bbwe!App", "fallback": "soundrecorder.exe", "name": "Ses Kaydedici", "process": "SoundRec.exe"},
    "voice recorder": {"target": "shell:AppsFolder\\Microsoft.WindowsSoundRecorder_8wekyb3d8bbwe!App", "fallback": "soundrecorder.exe", "name": "Voice Recorder", "process": "SoundRec.exe"},
    "ekran alintisi": {"target": "ms-screenclip:", "fallback": "SnippingTool.exe", "name": "Ekran Alıntısı Aracı", "process": "SnippingTool.exe"},
    "snipping tool": {"target": "ms-screenclip:", "fallback": "SnippingTool.exe", "name": "Snipping Tool", "process": "SnippingTool.exe"},
    "snip": {"target": "ms-screenclip:", "fallback": "SnippingTool.exe", "name": "Snipping Tool", "process": "SnippingTool.exe"},

    # Web Browsers
    "chrome": {"target": "shell:AppsFolder\\Chrome", "fallback": "chrome.exe", "name": "Google Chrome", "process": "chrome.exe"},
    "google chrome": {"target": "shell:AppsFolder\\Chrome", "fallback": "chrome.exe", "name": "Google Chrome", "process": "chrome.exe"},
    "google": {"target": "shell:AppsFolder\\Chrome", "fallback": "chrome.exe", "name": "Google Chrome", "process": "chrome.exe"},
    "edge": {"target": "microsoft-edge:", "fallback": "msedge.exe", "name": "Microsoft Edge", "process": "msedge.exe"},
    "microsoft edge": {"target": "microsoft-edge:", "fallback": "msedge.exe", "name": "Microsoft Edge", "process": "msedge.exe"},
    "tarayici": {"target": "shell:AppsFolder\\Chrome", "fallback": "microsoft-edge:", "name": "Web Tarayıcısı", "process": "chrome.exe"},
    "browser": {"target": "shell:AppsFolder\\Chrome", "fallback": "microsoft-edge:", "name": "Web Browser", "process": "chrome.exe"},

    # Coding & Development
    "vscode": {"target": "shell:AppsFolder\\Microsoft.VisualStudioCode", "fallback": "code.exe", "name": "Visual Studio Code", "process": "Code.exe"},
    "vs code": {"target": "shell:AppsFolder\\Microsoft.VisualStudioCode", "fallback": "code.exe", "name": "Visual Studio Code", "process": "Code.exe"},
    "visual studio code": {"target": "shell:AppsFolder\\Microsoft.VisualStudioCode", "fallback": "code.exe", "name": "Visual Studio Code", "process": "Code.exe"},
    "visual studio": {"target": "shell:AppsFolder\\Microsoft.VisualStudioCode", "fallback": "code.exe", "name": "Visual Studio Code", "process": "Code.exe"},

    # Communication & Social
    "discord": {"target": "shell:AppsFolder\\com.squirrel.Discord.Discord", "fallback": "Discord.exe", "name": "Discord", "process": "Discord.exe"},
    "whatsapp": {"target": "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App", "fallback": "WhatsApp.exe", "name": "WhatsApp", "process": "WhatsApp.exe"},
    "skype": {"target": "shell:AppsFolder\\Microsoft.SkypeApp_kzf8qxf38zg5c!App", "fallback": "Skype.exe", "name": "Skype", "process": "Skype.exe"},

    # Media & Entertainment
    "spotify": {"target": "shell:AppsFolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify", "fallback": "Spotify.exe", "name": "Spotify", "process": "Spotify.exe"},
    "muzik": {"target": "shell:AppsFolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify", "fallback": "Spotify.exe", "name": "Spotify", "process": "Spotify.exe"},
    "music": {"target": "shell:AppsFolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify", "fallback": "Spotify.exe", "name": "Spotify", "process": "Spotify.exe"},
    "vlc": {"target": "shell:AppsFolder\\{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}\\VideoLAN\\VLC\\vlc.exe", "fallback": "vlc.exe", "name": "VLC Media Player", "process": "vlc.exe"},
    "vlc media player": {"target": "shell:AppsFolder\\{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}\\VideoLAN\\VLC\\vlc.exe", "fallback": "vlc.exe", "name": "VLC Media Player", "process": "vlc.exe"},
    "capcut": {"target": "shell:AppsFolder\\Bytedance.CapCut", "fallback": "CapCut.exe", "name": "CapCut", "process": "CapCut.exe"},
    "voicemod": {"target": "shell:AppsFolder\\net.voicemod.desktop", "fallback": "Voicemod.exe", "name": "Voicemod", "process": "VoicemodDesktop.exe"},

    # Gaming & Launchers
    "steam": {"target": "shell:AppsFolder\\{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}\\Steam\\steam.exe", "fallback": "steam.exe", "name": "Steam", "process": "steam.exe"},
    "valorant": {"target": "shell:AppsFolder\\Microsoft.AutoGenerated.{B90C4CF3-5116-AEB7-2542-2440C94B666D}", "fallback": "C:\\Riot Games\\Riot Client\\RiotClientServices.exe", "name": "VALORANT", "process": "VALORANT.exe"},
    "riot client": {"target": "C:\\Riot Games\\Riot Client\\RiotClientServices.exe", "fallback": None, "name": "Riot Client", "process": "RiotClientServices.exe"},
    "tlauncher": {"target": "C:\\Users\\pc\\AppData\\Roaming\\.minecraft\\TLauncher.exe", "fallback": "TLauncher.exe", "name": "TLauncher", "process": "javaw.exe"},
    "minecraft": {"target": "C:\\Users\\pc\\AppData\\Roaming\\.minecraft\\TLauncher.exe", "fallback": "TLauncher.exe", "name": "Minecraft (TLauncher)", "process": "javaw.exe"},
    "roblox": {"target": "shell:AppsFolder\\com.Roblox.Player", "fallback": "RobloxPlayerBeta.exe", "name": "Roblox", "process": "RobloxPlayerBeta.exe"},
    "roblox player": {"target": "shell:AppsFolder\\com.Roblox.Player", "fallback": "RobloxPlayerBeta.exe", "name": "Roblox Player", "process": "RobloxPlayerBeta.exe"},
    "roblox studio": {"target": "C:\\Users\\pc\\AppData\\Local\\Roblox\\Versions\\version-30215da31a3b42e2\\RobloxStudioBeta.exe", "fallback": "RobloxStudioBeta.exe", "name": "Roblox Studio", "process": "RobloxStudioBeta.exe"},
    "bluestacks": {"target": "shell:AppsFolder\\BlueStacks_nxt", "fallback": "HD-Player.exe", "name": "BlueStacks 5", "process": "HD-Player.exe"},
    "bluestacks 5": {"target": "shell:AppsFolder\\BlueStacks_nxt", "fallback": "HD-Player.exe", "name": "BlueStacks 5", "process": "HD-Player.exe"},
    "xbox": {"target": "shell:AppsFolder\\Microsoft.GamingApp_8wekyb3d8bbwe!Microsoft.Xbox.App", "fallback": "XboxApp.exe", "name": "Xbox", "process": "XboxApp.exe"},
    "chatgpt": {"target": "shell:AppsFolder\\OpenAI.ChatGPT-Desktop_2p2nqsd0c76g0!ChatGPT", "fallback": "ChatGPT.exe", "name": "ChatGPT Classic", "process": "ChatGPT.exe"},
    "speedtest": {"target": "shell:AppsFolder\\Ookla.SpeedtestbyOokla_43tkc6nmykmb6!App", "fallback": "Speedtest.exe", "name": "Speedtest", "process": "Speedtest.exe"},
    "winrar": {"target": "shell:AppsFolder\\{6D809377-6AF0-444B-8957-A3773F02200E}\\WinRAR\\WinRAR.exe", "fallback": "winrar.exe", "name": "WinRAR", "process": "WinRAR.exe"},

    # Steam Games by Name
    "the forest": {"target": "steam://rungameid/242760", "fallback": None, "name": "The Forest", "process": "TheForest.exe"},
    "rainbow six": {"target": "steam://rungameid/359550", "fallback": None, "name": "Tom Clancy's Rainbow Six Siege", "process": "RainbowSix.exe"},
    "rainbow six siege": {"target": "steam://rungameid/359550", "fallback": None, "name": "Tom Clancy's Rainbow Six Siege", "process": "RainbowSix.exe"},
    "r6": {"target": "steam://rungameid/359550", "fallback": None, "name": "Tom Clancy's Rainbow Six Siege", "process": "RainbowSix.exe"},
    "wallpaper engine": {"target": "steam://rungameid/431960", "fallback": None, "name": "Wallpaper Engine", "process": "wallpaper32.exe"},
    "backrooms": {"target": "steam://rungameid/2141730", "fallback": None, "name": "Backrooms Escape Together", "process": "Backrooms.exe"},
    "backrooms escape together": {"target": "steam://rungameid/2141730", "fallback": None, "name": "Backrooms Escape Together", "process": "Backrooms.exe"},
    "redmatch 2": {"target": "steam://rungameid/1280770", "fallback": None, "name": "Redmatch 2", "process": "Redmatch2.exe"},
    "ultimate custom night": {"target": "steam://rungameid/871720", "fallback": None, "name": "Ultimate Custom Night", "process": "UltimateCustomNight.exe"},
    "ucn": {"target": "steam://rungameid/871720", "fallback": None, "name": "Ultimate Custom Night", "process": "UltimateCustomNight.exe"}
}

# ---------------------------------------------------------
# DYNAMIC APPLICATION DISCOVERY & INDEXING
# ---------------------------------------------------------

def scan_windows_start_apps() -> List[Dict[str, str]]:
    """Runs PowerShell Get-StartApps with UTF-8 encoding to retrieve all registered Windows apps."""
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Depth 2"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=12)
        if result.returncode == 0 and result.stdout.strip():
            raw_data = json.loads(result.stdout)
            if isinstance(raw_data, list):
                # Save cache to apps.json for instant future restarts
                with open(APPS_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(raw_data, f, indent=4, ensure_ascii=False)
                return raw_data
    except Exception as e:
        print(f"[AppLauncher] PowerShell StartApps scan warning: {e}")
        
    # Fallback to local cache if powershell fails
    if os.path.exists(APPS_CACHE_FILE):
        try:
            with open(APPS_CACHE_FILE, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
            
    return []

def scan_desktop_and_start_menu_shortcuts() -> List[Dict[str, str]]:
    """Scans Desktop and Start Menu for .lnk shortcuts."""
    shortcuts = []
    search_dirs = [
        os.path.expanduser("~/Desktop"),
        "C:\\Users\\Public\\Desktop",
        os.path.expandvars("%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs"),
        os.path.expandvars("%PROGRAMDATA%\\Microsoft\\Windows\\Start Menu\\Programs")
    ]
    
    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        for root, _, files in os.walk(sdir):
            for file in files:
                if file.lower().endswith(('.lnk', '.url')):
                    name = os.path.splitext(file)[0]
                    full_path = os.path.join(root, file)
                    shortcuts.append({"Name": name, "AppID": full_path})
                    
    return shortcuts

def initialize_index(force_refresh: bool = False):
    """Loads and compiles the global app index."""
    global _APPS_INDEX, _INDEX_LOADED
    if _INDEX_LOADED and not force_refresh:
        return
        
    apps_map = {}
    
    # 1. Load from cache file first for instant startup
    if os.path.exists(APPS_CACHE_FILE):
        try:
            with open(APPS_CACHE_FILE, "r", encoding="utf-8-sig") as f:
                cached = json.load(f)
                for item in cached:
                    name = item.get("Name", "").strip()
                    appid = item.get("AppID", "").strip()
                    if name and appid:
                        apps_map[name.lower()] = {"Name": name, "AppID": appid}
        except Exception as e:
            print(f"[AppLauncher] Error reading cached apps: {e}")

    # 2. Add Desktop & Start Menu Shortcuts
    shortcuts = scan_desktop_and_start_menu_shortcuts()
    for item in shortcuts:
        name = item["Name"].strip()
        appid = item["AppID"].strip()
        if name and name.lower() not in apps_map:
            apps_map[name.lower()] = {"Name": name, "AppID": appid}
            
    # 3. If empty or requested, do fresh PowerShell scan
    if not apps_map or force_refresh:
        scanned = scan_windows_start_apps()
        for item in scanned:
            name = item.get("Name", "").strip()
            appid = item.get("AppID", "").strip()
            if name and appid:
                apps_map[name.lower()] = {"Name": name, "AppID": appid}
                
    _APPS_INDEX = list(apps_map.values())
    _INDEX_LOADED = True
    print(f"[AppLauncher] Indexed {len(_APPS_INDEX)} applications successfully.")

# ---------------------------------------------------------
# INTELLIGENT APPLICATION RESOLVER / MATCHER
# ---------------------------------------------------------

def resolve_app_target(query: str) -> Optional[Dict[str, Any]]:
    """
    Given a user query (e.g. 'hesap makinesini aç', 'open calculator', 'spotify', 'chrome'),
    resolves to the exact target path, AppID, or URI.
    """
    initialize_index()
    
    candidates = []
    # Candidate 1: Normalized with stemming
    c1 = normalize_text(query, apply_stemming=True)
    if c1:
        candidates.append(c1)
        
    # Candidate 2: Normalized without stemming
    c2 = normalize_text(query, apply_stemming=False)
    if c2 and c2 != c1:
        candidates.append(c2)
        
    # Candidate 3: Raw stripped
    c3 = re.sub(r"[^\w\s]", "", query.lower().strip())
    if c3 and c3 not in candidates:
        candidates.append(c3)
        
    if not candidates:
        return None
        
    # 1. Exact or substring match in SYSTEM_ALIASES for any candidate
    for cand in candidates:
        if cand in SYSTEM_ALIASES:
            return SYSTEM_ALIASES[cand]
            
    for cand in candidates:
        for alias_key, data in SYSTEM_ALIASES.items():
            if alias_key == cand or f" {alias_key} " in f" {cand} " or f" {cand} " in f" {alias_key} ":
                return data

    # 2. Match against indexed StartApps & Shortcuts
    best_match = None
    best_score = 0.0
    
    for cand in candidates:
        for item in _APPS_INDEX:
            name = item.get("Name", "")
            appid = item.get("AppID", "")
            norm_name = normalize_text(name, apply_stemming=False)
            
            # A. Exact match
            if cand == norm_name:
                target = f"shell:AppsFolder\\{appid}" if not appid.startswith("shell:") and not os.path.isabs(appid) and not "://" in appid else appid
                return {"target": target, "fallback": None, "name": name, "process": None}
                
            # B. Substring match
            if cand in norm_name or norm_name in cand:
                score = len(cand) / max(len(norm_name), 1)
                if score > best_score:
                    best_score = score
                    best_match = (name, appid)
                    
            # C. Fuzzy similarity (SequenceMatcher)
            similarity = difflib.SequenceMatcher(None, cand, norm_name).ratio()
            if similarity > 0.70 and similarity > best_score:
                best_score = similarity
                best_match = (name, appid)
                
    if best_match and best_score >= 0.45:
        name, appid = best_match
        target = f"shell:AppsFolder\\{appid}" if not appid.startswith("shell:") and not os.path.isabs(appid) and not "://" in appid else appid
        return {"target": target, "fallback": None, "name": name, "process": None}
        
    # 3. Direct executable check in system PATH
    for cand in candidates:
        which_path = shutil.which(cand) or shutil.which(f"{cand}.exe")
        if which_path:
            return {"target": which_path, "fallback": None, "name": cand.capitalize(), "process": os.path.basename(which_path)}
            
    # 4. Check if user provided direct URI (e.g. steam://, ms-settings:, https://)
    if "://" in query or query.startswith("ms-"):
        return {"target": query, "fallback": None, "name": query, "process": None}
        
    return None

# ---------------------------------------------------------
# ZERO-FAILURE MULTI-TIER LAUNCH ENGINE
# ---------------------------------------------------------

def _minimize_jarvis():
    """Notifies the Jarvis UI web server to minimize if running."""
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:8000/api/minimize", headers={'User-Agent': 'JarvisLauncher/1.0'})
        urllib.request.urlopen(req, timeout=0.5)
    except Exception:
        pass

def launch_target(target: str) -> bool:
    """Executes a target using OS APIs."""
    if not target:
        return False
        
    # Method 1: os.startfile (Windows native ShellExecute)
    try:
        os.startfile(target)
        return True
    except Exception as err1:
        # Method 2: ctypes ShellExecuteW
        try:
            res = ctypes.windll.shell32.ShellExecuteW(None, "open", target, None, None, 1)
            if res > 32:
                return True
        except Exception:
            pass
            
        # Method 3: subprocess explorer / start
        try:
            if target.startswith("shell:AppsFolder"):
                subprocess.Popen(["explorer.exe", target], shell=True)
                return True
            else:
                subprocess.Popen(f'start "" "{target}"', shell=True)
                return True
        except Exception as err3:
            print(f"[AppLauncher] Launch error for '{target}': {err1}, {err3}")
            return False

def open_app(app_name: str) -> str:
    """
    Public entrypoint to open any application or game on Windows.
    Guarantees maximum accuracy, multi-tier fallback, and fast execution.
    """
    if not app_name or not app_name.strip():
        return "Please specify an application name to open."
        
    app_info = resolve_app_target(app_name)
    
    if app_info:
        target = app_info.get("target")
        fallback = app_info.get("fallback")
        display_name = app_info.get("name", app_name)
        
        # Try primary target
        success = launch_target(target)
        
        # If primary failed, try fallback
        if not success and fallback:
            print(f"[AppLauncher] Primary target failed, attempting fallback: {fallback}")
            success = launch_target(fallback)
            
        if success:
            _minimize_jarvis()
            return f"Successfully opened {display_name}."
            
    # If not found in index, try direct system start or safe start search
    clean_name = normalize_text(app_name, apply_stemming=False)
    
    # Try direct startfile with clean_name
    try:
        os.startfile(clean_name)
        _minimize_jarvis()
        return f"Successfully launched {clean_name}."
    except Exception:
        pass
        
    # Safe Windows Start Menu Search with Unicode Clipboard Fallback
    try:
        import pyautogui
        import pyperclip
        pyautogui.FAILSAFE = False
        
        pyperclip.copy(app_name)
        pyautogui.hotkey('ctrl', 'esc')
        time.sleep(0.4)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
        pyautogui.press('enter')
        time.sleep(0.5)
        _minimize_jarvis()
        return f"Dispatched launch command for {app_name} via Windows Start."
    except Exception as e:
        return f"Could not find or launch {app_name}: {e}"

# ---------------------------------------------------------
# APPLICATION TERMINATION (CLOSE APP)
# ---------------------------------------------------------

def close_app(app_name: str) -> str:
    """
    Terminates / closes a running application.
    """
    if not app_name:
        return "Please specify an application name to close."
        
    app_info = resolve_app_target(app_name)
    process_name = None
    display_name = app_name
    
    if app_info:
        process_name = app_info.get("process")
        display_name = app_info.get("name", app_name)
        
    if not process_name:
        clean = normalize_text(app_name, apply_stemming=False).replace(" ", "")
        process_name = f"{clean}.exe"
        
    try:
        # Run taskkill
        res = subprocess.run(["taskkill", "/F", "/IM", process_name], capture_output=True, text=True)
        if res.returncode == 0:
            return f"Successfully closed {display_name}."
        else:
            # Try without .exe or match via powershell Get-Process
            ps_cmd = f"Get-Process | Where-Object {{ $_.ProcessName -like '*{normalize_text(app_name, apply_stemming=False)}*' }} | Stop-Process -Force"
            ps_res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
            if ps_res.returncode == 0:
                return f"Successfully closed {display_name}."
            return f"Application {display_name} is not currently running or could not be closed."
    except Exception as e:
        return f"Error closing {display_name}: {e}"

# Pre-warm index on module load
try:
    initialize_index()
except Exception as e:
    print(f"[AppLauncher] Pre-warm note: {e}")
