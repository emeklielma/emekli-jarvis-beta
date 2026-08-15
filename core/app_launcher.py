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
import subprocess
from rapidfuzz import fuzz, process
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

NOISE_WORDS = {
    'lutfen', 'ac', 'acarmisin', 'acabilir', 'acabilir misin', 'aciver', 'baslat', 'calistir', 
    'goster', 'getir', 'ver', 'uygulamasi', 'uygulamasini', 'uygulamayi', 'uygulamalar', 'uygulamalari',
    'programi', 'programini', 'program', 'programlar', 'programlari', 
    'oyun', 'oyunu', 'oyununu', 'oyunlar', 'oyunlari',
    'penceresi', 'penceresini', 'sekmesi', 'sekmesini',
    'open', 'launch', 'start', 'run', 'show', 'bring', 'please', 'app', 'application', 'game'
}

def clean_word_stem(word: str) -> str:
    word = re.sub(r"'[a-z0-9]+$", "", word, flags=re.IGNORECASE)
    if len(word) > 5:
        word = re.sub(r"(lerini|larini)$", "", word)
        word = re.sub(r"(sini|sini|sunu|sunu)$", "si", word)
        word = re.sub(r"(ini|ini|unu|unu)$", "i", word)
        word = re.sub(r"(yi|yi|yu|yu)$", "", word)
        word = re.sub(r"(yi|yi)$", "", word)
    return word

def normalize_text(text: str, apply_stemming: bool = True) -> str:
    if not text: return ""
    text = text.lower().strip()
    for k, v in TR_CHAR_MAP.items():
        text = text.replace(k, v)
    raw_words = [re.sub(r"[^\w\s']", "", w) for w in text.split() if w]
    filtered_words = []
    for w in raw_words:
        base_w = re.sub(r"'[a-z0-9]+$", "", w, flags=re.IGNORECASE)
        if base_w in NOISE_WORDS or w in NOISE_WORDS:
            continue
        if apply_stemming:
            cleaned_w = clean_word_stem(w)
            if cleaned_w in NOISE_WORDS: continue
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
    "hesap makinesi": {"target": "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", "name": "Hesap Makinesi", "process": "CalculatorApp.exe"},
    "calculator": {"target": "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", "name": "Calculator", "process": "CalculatorApp.exe"},
    "not defteri": {"target": "shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", "name": "Not Defteri", "process": "Notepad.exe"},
    "notepad": {"target": "shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", "name": "Notepad", "process": "Notepad.exe"},
    "ayarlar": {"target": "ms-settings:", "name": "Windows Ayarlar", "process": "SystemSettings.exe"},
    "settings": {"target": "ms-settings:", "name": "Settings", "process": "SystemSettings.exe"},
    "gorev yoneticisi": {"target": "taskmgr.exe", "name": "Görev Yöneticisi", "process": "Taskmgr.exe"},
    "task manager": {"target": "taskmgr.exe", "name": "Task Manager", "process": "Taskmgr.exe"},
    "dosya gezgini": {"target": "explorer.exe", "name": "Dosya Gezgini", "process": "explorer.exe"},
    "explorer": {"target": "explorer.exe", "name": "File Explorer", "process": "explorer.exe"},
    "paint": {"target": "shell:AppsFolder\\Microsoft.Paint_8wekyb3d8bbwe!App", "name": "Paint", "process": "mspaint.exe"},
    "terminal": {"target": "shell:AppsFolder\\Microsoft.WindowsTerminal_8wekyb3d8bbwe!App", "name": "Terminal", "process": "WindowsTerminal.exe"},
    "cmd": {"target": "cmd.exe", "name": "Command Prompt", "process": "cmd.exe"},
    "powershell": {"target": "powershell.exe", "name": "PowerShell", "process": "powershell.exe"},
    "chrome": {"target": "shell:AppsFolder\\Chrome", "name": "Google Chrome", "process": "chrome.exe"},
    "google chrome": {"target": "shell:AppsFolder\\Chrome", "name": "Google Chrome", "process": "chrome.exe"},
    "edge": {"target": "microsoft-edge:", "name": "Microsoft Edge", "process": "msedge.exe"},
    "vscode": {"target": "shell:AppsFolder\\Microsoft.VisualStudioCode", "name": "Visual Studio Code", "process": "Code.exe"},
    "discord": {"target": "shell:AppsFolder\\com.squirrel.Discord.Discord", "name": "Discord", "process": "Discord.exe"},
    "spotify": {"target": "shell:AppsFolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify", "name": "Spotify", "process": "Spotify.exe"},
    "steam": {"target": "steam://open/main", "name": "Steam", "process": "steam.exe"},
    "valorant": {"target": "C:\\Riot Games\\Riot Client\\RiotClientServices.exe", "name": "VALORANT", "process": "VALORANT.exe"},
    "roblox": {"target": "shell:AppsFolder\\com.Roblox.Player", "name": "Roblox", "process": "RobloxPlayerBeta.exe"},
}

def scan_windows_start_apps() -> List[Dict[str, str]]:
    try:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Depth 2"]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            raw_data = json.loads(result.stdout)
            if isinstance(raw_data, list):
                with open(APPS_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(raw_data, f, indent=4, ensure_ascii=False)
                return raw_data
    except Exception:
        pass
    if os.path.exists(APPS_CACHE_FILE):
        try:
            with open(APPS_CACHE_FILE, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def scan_desktop_and_start_menu_shortcuts() -> List[Dict[str, str]]:
    shortcuts = []
    search_dirs = [
        os.path.expanduser("~/Desktop"),
        "C:\\Users\\Public\\Desktop",
        os.path.expandvars("%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs"),
        os.path.expandvars("%PROGRAMDATA%\\Microsoft\\Windows\\Start Menu\\Programs")
    ]
    for sdir in search_dirs:
        if not os.path.exists(sdir): continue
        for root, _, files in os.walk(sdir):
            for file in files:
                if file.lower().endswith(('.lnk', '.url')):
                    shortcuts.append({"Name": os.path.splitext(file)[0], "AppID": os.path.join(root, file)})
    return shortcuts

def initialize_index(force_refresh: bool = False):
    global _APPS_INDEX, _INDEX_LOADED
    if _INDEX_LOADED and not force_refresh: return
    apps_map = {}
    if os.path.exists(APPS_CACHE_FILE):
        try:
            with open(APPS_CACHE_FILE, "r", encoding="utf-8-sig") as f:
                cached = json.load(f)
                for item in cached:
                    name = item.get("Name", "").strip()
                    appid = item.get("AppID", "").strip()
                    if name and appid: apps_map[name.lower()] = {"Name": name, "AppID": appid}
        except Exception: pass
    shortcuts = scan_desktop_and_start_menu_shortcuts()
    for item in shortcuts:
        name = item["Name"].strip()
        appid = item["AppID"].strip()
        if name and name.lower() not in apps_map: apps_map[name.lower()] = {"Name": name, "AppID": appid}
    if not apps_map or force_refresh:
        scanned = scan_windows_start_apps()
        for item in scanned:
            name = item.get("Name", "").strip()
            appid = item.get("AppID", "").strip()
            if name and appid: apps_map[name.lower()] = {"Name": name, "AppID": appid}
    _APPS_INDEX = list(apps_map.values())
    _INDEX_LOADED = True

def resolve_app_target(query: str) -> Optional[Dict[str, Any]]:
    initialize_index()
    c1 = normalize_text(query, apply_stemming=True)
    c2 = normalize_text(query, apply_stemming=False)
    candidates = list(dict.fromkeys([c for c in [c1, c2, query.lower().strip()] if c]))
    
    if not candidates: return None
    
    # 1. Alias Match
    for cand in candidates:
        if cand in SYSTEM_ALIASES: return SYSTEM_ALIASES[cand]
    
    # 2. Rapidfuzz Match against Index
    app_names = [item["Name"] for item in _APPS_INDEX]
    best_match = None
    best_score = 0
    best_item = None
    
    for cand in candidates:
        result = process.extractOne(cand, app_names, scorer=fuzz.partial_ratio)
        if result:
            match_name, score, index = result
            if score > best_score:
                best_score = score
                best_item = _APPS_INDEX[index]
    
    if best_item and best_score > 70:
        appid = best_item["AppID"]
        target = f"shell:AppsFolder\\{appid}" if not appid.startswith("shell:") and not os.path.isabs(appid) and not "://" in appid else appid
        return {"target": target, "name": best_item["Name"], "process": None}
        
    # 3. Path/Direct execute
    for cand in candidates:
        which_path = shutil.which(cand) or shutil.which(f"{cand}.exe")
        if which_path:
            return {"target": which_path, "name": cand.capitalize(), "process": os.path.basename(which_path)}
            
    if "://" in query or query.startswith("ms-"):
        return {"target": query, "name": query, "process": None}
    return None

def launch_target(target: str) -> bool:
    if not target: return False
    try:
        if target.startswith("shell:AppsFolder"):
            subprocess.Popen(f'explorer.exe {target}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(f'start "" "{target}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def open_app(app_name: str) -> str:
    app_info = resolve_app_target(app_name)
    if app_info:
        if launch_target(app_info.get("target")):
            return f"Successfully opened {app_info.get('name')}."
            
    # Safe Windows Start Menu Search fallback
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
        return f"Dispatched launch command for {app_name} via Windows Start."
    except Exception as e:
        return f"Could not find or launch {app_name}."

def close_app(app_name: str) -> str:
    app_info = resolve_app_target(app_name)
    process_name = app_info.get("process") if app_info else f"{normalize_text(app_name, apply_stemming=False).replace(' ', '')}.exe"
    display_name = app_info.get("name", app_name) if app_info else app_name
    try:
        subprocess.Popen(f'taskkill /F /IM {process_name}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Successfully closed {display_name}."
    except Exception as e:
        return f"Error closing {display_name}."
