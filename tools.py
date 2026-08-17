import os
import datetime
import urllib.parse
import subprocess
import pyautogui
import time
import urllib.request
import xml.etree.ElementTree as ET
import threading
import uuid
import re

# server.py, kesme (mikrofon "interrupt" butonu) durumunu buradan set eder;
# tools.py'nin server.py'yi import etmesi gerekmeden (döngüsel import olmadan)
# run_terminal_command'ın bekleme döngüsünde bu bayrağı kontrol edebilmesi için
# tek gerçek kaynak (single source of truth) burada tutuluyor.
INTERRUPT_FLAG = False

# server.py, onay isteğini UI'ya iletecek fonksiyonu (ui_queue.put) buraya bağlar.
# Bağlanmamışsa (örn. CLI modu / main.py) onay istenemeyeceği için komut reddedilir.
approval_request_sink = None

# request_id -> {"event": threading.Event, "approved": bool|None, "command": str}
pending_approvals = {}
pending_approvals_lock = threading.Lock()

APPROVAL_TIMEOUT_SECONDS = 15.0
APPROVAL_POLL_INTERVAL_SECONDS = 0.2


# Kategori A: salt-okunur, state değiştirmeyen komutlar — tam eşleşme (^...$),
# wildcard YOK. Yeni bir pattern eklerken de aynı disiplini koru: gevşek/joker
# karakterli regex, whitelist'in tüm amacını (öngörülebilirlik) boşa çıkarır.
_READONLY_WHITELIST_PATTERNS = [
    re.compile(r"^Get-Date$", re.IGNORECASE),
    re.compile(r"^ipconfig$", re.IGNORECASE),
    re.compile(r"^Get-NetIPAddress$", re.IGNORECASE),
    re.compile(r"^Get-Volume$", re.IGNORECASE),
    re.compile(r"^Get-Process$", re.IGNORECASE),
    re.compile(r"^\(Get-WmiObject Win32_Battery\)\.EstimatedChargeRemaining$", re.IGNORECASE),
    re.compile(r"^netsh wlan show interfaces$", re.IGNORECASE),
    re.compile(r"^whoami$", re.IGNORECASE),
    re.compile(r"^hostname$", re.IGNORECASE),
    re.compile(r"^Get-CimInstance Win32_OperatingSystem$", re.IGNORECASE),
]

# Kategori C: whitelist'e HİÇBİR ZAMAN girmeyecek komut sınıfları. Burada bir
# "engelleme" mekanizması yok çünkü _is_whitelisted zaten varsayılan olarak
# False dönüyor (fail-closed) — bu liste sadece niyet belgesi: ileride birisi
# whitelist'i genişletirken bu kategorilere ait bir pattern EKLEMESİN diye.
#   - shutdown /s, shutdown /r          (kapatma/yeniden başlatma, geri alınamaz)
#   - Remove-Item -Recurse -Force, format, diskpart  (yıkıcı disk/dosya işlemleri)
#   - Set-ExecutionPolicy                (PowerShell güvenlik politikası)
#   - Set-MpPreference -Disable...       (Defender kapatma)
#   - netsh advfirewall ... state off    (Firewall kapatma)
#   - reg add / reg delete (özellikle HKLM)  (registry değişikliği)
#   - net user / New-LocalUser            (kullanıcı hesabı yönetimi)
#   - Invoke-Expression, IEX, ... | iex   (uzaktan/dinamik kod çalıştırma)
# Bu kategoriler her zaman _await_approval() üzerinden kullanıcı onayına düşer.


def _is_whitelisted(command):
    """Kategori A (salt-okunur) komutlar için onaysız çalıştırmaya izin verir.

    Diğer her şey (Kategori B/C dahil) varsayılan olarak reddedilir/onay
    ister — fail-closed. Whitelist'e yeni pattern eklerken her zaman tam
    eşleşme (^...$) kullan, asla wildcard/serbest regex ekleme.
    """
    stripped = command.strip()
    return any(pattern.match(stripped) for pattern in _READONLY_WHITELIST_PATTERNS)

# Original Tools
def open_website(url):
    if not url.startswith("http"): url = "https://" + url
    os.startfile(url)
    return f"Successfully opened {url}."

def search_youtube(query):
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded_query}"
    os.startfile(url)
    return f"Successfully searched YouTube for: {query}."

def open_application(app_name):
    app_map = {"notepad": "notepad", "calculator": "calc", "calc": "calc", "chrome": "chrome", "spotify": "spotify", "edge": "msedge", "explorer": "explorer"}
    cmd = app_map.get(app_name.lower())
    if cmd:
        os.system(f"start {cmd}")
        return f"Successfully opened {app_name}."
    else:
        os.system(f"start {app_name}")
        return f"Attempted to open {app_name} via Windows Start."

def get_time_and_date():
    now = datetime.datetime.now()
    return now.strftime("The current date is %B %d, %Y, and the time is %I:%M %p.")

# Kapatılması ASLA izin verilmeyecek kritik Windows süreçleri — kapatılırlarsa
# masaüstü/oturum/servisler çöker. Karşılaştırma case-insensitive ve .exe'siz
# taban isim üzerinden yapılır.
_CRITICAL_PROCESS_BLOCKLIST = {
    "explorer", "csrss", "wininit", "winlogon", "services", "lsass", "svchost", "system",
}

# Belge/proje düzenleyen, kaydedilmemiş çalışma kaybı riski yüksek uygulamalar —
# bunlar için taskkill'den önce kullanıcı onayı istenir. Kritik sistem süreci
# değiller (kapatılmaları güvenli), sadece "veri kaybı" riski taşıyorlar.
_UNSAVED_WORK_RISK_APPS = {
    "winword", "excel", "powerpoint", "code", "notepad++", "photoshop",
    "illustrator", "premiere", "aftereffects", "blender", "devenv",
    "pycharm64", "idea64",
}

def close_application(app_name):
    """taskkill /IM {app}.exe /F ile tek bir uygulamayı kapatır.

    run_terminal_command'a hiç gitmez — sabit bir komut şablonu ve kritik
    süreç blocklist'i ile dar kapsamlı, kendi başına güvenli bir tool.
    _UNSAVED_WORK_RISK_APPS'teki uygulamalar için mevcut onay mekanizması
    (pending_approvals) üzerinden kullanıcı onayı istenir.
    """
    base_name = app_name.strip()
    if base_name.lower().endswith(".exe"):
        base_name = base_name[:-4]

    if base_name.lower() in _CRITICAL_PROCESS_BLOCKLIST:
        return f"Reddedildi: '{base_name}' kritik bir sistem süreci, kapatılamaz."

    if not base_name:
        return "Reddedildi: Uygulama adı boş."

    if base_name.lower() in _UNSAVED_WORK_RISK_APPS:
        friendly_message = f"'{base_name}' kapatılsın mı? Kaydedilmemiş değişiklikler kaybolabilir."
        approved, reason = _await_approval(friendly_message)
        if not approved:
            return f"Uygulama kapatılmadı: {reason}"

    try:
        result = subprocess.run(
            ["taskkill", "/IM", f"{base_name}.exe", "/F"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return f"Successfully closed {base_name}."
        else:
            return f"Command failed: {result.stderr.strip() or result.stdout.strip()}"
    except Exception as e:
        return f"Error closing application: {e}"

_TR_LOWER_MAP = str.maketrans({
    "İ": "i", "I": "i", "ı": "i",
    "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o",
    "Ç": "c", "ç": "c",
})


def _normalize_tr(s):
    """Türkçe karakterleri (İ/I/ı, ş, ğ, ü, ö, ç) ASCII eşdeğerlerine indirger
    ve küçük harfe çevirir. Python'un locale-bağımsız str.lower()'ı "İ" için
    ortama göre "i" veya "i" + kombine nokta (U+0307) üretebildiğinden —
    ki bu ikisi birbirine eşit değildir — klasör adı ve arama sorgusu
    karşılaştırmalarında ham .lower() yerine bu fonksiyon kullanılır.
    """
    if not s:
        return ""
    return s.translate(_TR_LOWER_MAP).lower()


# search_files, move_file ve copy_file'ın izin verdiği tek klasör kümesi.
# Anahtarlar kasıtlı olarak ASCII (Türkçe karaktersiz) — _normalize_tr ile
# karşılaştırıldığında ortam/Unicode-normalizasyon farklarından bağımsız
# kalır. Path traversal veya mutlak yol ile bu klasörlerin dışına çıkmak
# her zaman reddedilir (fail-closed) — bkz. _resolve_within_allowed_folders.
_ALLOWED_FOLDERS = {
    "masaustu": os.path.join(os.path.expanduser("~"), "Desktop"),
    "belgeler": os.path.join(os.path.expanduser("~"), "Documents"),
    "indirilenler": os.path.join(os.path.expanduser("~"), "Downloads"),
    "resimler": os.path.join(os.path.expanduser("~"), "Pictures"),
}

_SYSTEM_FOLDER_PREFIXES = [
    os.path.normcase(os.path.expandvars(r"%SystemRoot%")),
    os.path.normcase(os.path.expandvars(r"%ProgramFiles%")),
    os.path.normcase(os.path.expandvars(r"%ProgramFiles(x86)%")),
]


def _resolve_within_allowed_folders(path):
    """Bir yolu 4 standart klasörden biriyle sınırlar.

    Girdi mutlak bir yol, göreli bir yol veya sadece bir dosya adı olabilir.
    Sonuç, os.path.realpath ile normalize edildikten sonra izinli klasör
    köklerinden biriyle başlamıyorsa (".." veya sembolik link ile dışarı
    taşma dahil) None döner — çağıran bunu reddetmelidir.
    """
    real = os.path.realpath(os.path.abspath(path))
    real_cn = os.path.normcase(real)
    for root in _ALLOWED_FOLDERS.values():
        root_cn = os.path.normcase(os.path.realpath(root))
        if real_cn == root_cn or real_cn.startswith(root_cn + os.sep):
            return real
    return None


def _is_system_path(path):
    real_cn = os.path.normcase(os.path.realpath(os.path.abspath(path)))
    return any(real_cn.startswith(prefix) for prefix in _SYSTEM_FOLDER_PREFIXES if prefix)


def search_files(query, folder=None):
    """Standart kullanıcı klasörlerinde (Masaüstü, Belgeler, İndirilenler,
    Resimler) dosya adına göre arama yapar. folder verilirse arama sadece o
    klasörle sınırlanır; verilmezse dördü de taranır. Bu dört klasörün
    dışına asla çıkılmaz (path traversal denemeleri reddedilir).
    """
    if not query or not query.strip():
        return "Reddedildi: Arama sorgusu boş."

    if folder:
        key = _normalize_tr(folder.strip())
        if key not in _ALLOWED_FOLDERS:
            return (
                f"Reddedildi: '{folder}' izinli klasörlerden biri değil. "
                f"İzinli klasörler: {', '.join(_ALLOWED_FOLDERS.keys())}."
            )
        search_roots = {key: _ALLOWED_FOLDERS[key]}
    else:
        search_roots = _ALLOWED_FOLDERS

    query_lower = _normalize_tr(query.strip())
    matches = []
    for root in search_roots.values():
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # Her sonucun gerçekten izinli kök altında kaldığını garanti eder
            # (sembolik link ile dışarı çıkma ihtimaline karşı ekstra kontrol).
            if _resolve_within_allowed_folders(dirpath) is None:
                dirnames[:] = []
                continue
            for name in filenames:
                if query_lower in _normalize_tr(name):
                    matches.append(os.path.join(dirpath, name))
                    if len(matches) >= 50:
                        break
            if len(matches) >= 50:
                break
        if len(matches) >= 50:
            break

    if not matches:
        return f"'{query}' için sonuç bulunamadı."
    return f"{len(matches)} sonuç bulundu:\n" + "\n".join(matches)


def move_file(source, destination):
    return _relocate_file(source, destination, move=True)


def copy_file(source, destination):
    return _relocate_file(source, destination, move=False)


def _relocate_file(source, destination, move):
    """move_file/copy_file'ın ortak mantığı.

    Onay kuralları:
      a) hedef dosya zaten varsa (üzerine yazma riski) -> onay iste.
      b) hedef sistem/program klasöründeyse -> onay iste (kaynak/hedef zaten
         _ALLOWED_FOLDERS ile sınırlı olduğundan pratikte tetiklenmez, ama
         ekstra güvenlik katmanı olarak duruyor).
      c) diğer tüm durumlarda (standart klasörler arası basit taşıma/kopyalama)
         onaysız direkt çalışır.
    """
    import shutil

    src_real = _resolve_within_allowed_folders(source)
    if src_real is None:
        return f"Reddedildi: Kaynak '{source}' izinli klasörlerin (Masaüstü, Belgeler, İndirilenler, Resimler) dışında."
    if not os.path.isfile(src_real):
        return f"Reddedildi: Kaynak dosya bulunamadı: {source}"

    dst_real = _resolve_within_allowed_folders(destination)
    if dst_real is None:
        return f"Reddedildi: Hedef '{destination}' izinli klasörlerin (Masaüstü, Belgeler, İndirilenler, Resimler) dışında."

    # destination bir klasörse dosya adını kaynaktan miras al.
    if os.path.isdir(dst_real):
        dst_real = os.path.join(dst_real, os.path.basename(src_real))
        dst_real = _resolve_within_allowed_folders(dst_real) or dst_real

    action_word = "taşınsın" if move else "kopyalansın"

    if os.path.exists(dst_real):
        approved, reason = _await_approval(
            f"'{os.path.basename(src_real)}' dosyası '{dst_real}' konumuna {action_word} mı? "
            f"Hedefte aynı isimde bir dosya zaten var, üzerine yazılacak."
        )
        if not approved:
            return f"İşlem yapılmadı: {reason}"
    elif _is_system_path(dst_real):
        approved, reason = _await_approval(
            f"'{os.path.basename(src_real)}' dosyası sistem/program klasörüne ({dst_real}) {action_word} mı?"
        )
        if not approved:
            return f"İşlem yapılmadı: {reason}"

    try:
        os.makedirs(os.path.dirname(dst_real), exist_ok=True)
        if move:
            shutil.move(src_real, dst_real)
            return f"'{src_real}' başarıyla '{dst_real}' konumuna taşındı."
        else:
            shutil.copy2(src_real, dst_real)
            return f"'{src_real}' başarıyla '{dst_real}' konumuna kopyalandı."
    except Exception as e:
        return f"Error: {e}"


def _await_approval(command):
    """Onay isteğini UI'ya gönderir ve kullanıcı yanıtını (approve/deny/timeout/
    interrupt) senkron olarak bekler. Dönüş: (approved: bool, reason: str|None).
    """
    if approval_request_sink is None:
        return False, "Onay mekanizması bağlı değil (UI bağlantısı yok)."

    request_id = str(uuid.uuid4())
    event = threading.Event()
    with pending_approvals_lock:
        pending_approvals[request_id] = {"event": event, "approved": None, "command": command}

    try:
        approval_request_sink({"type": "confirm_request", "id": request_id, "command": command})

        elapsed = 0.0
        while elapsed < APPROVAL_TIMEOUT_SECONDS:
            if INTERRUPT_FLAG:
                return False, "Kullanıcı işlemi kesti (interrupt)."
            if event.wait(APPROVAL_POLL_INTERVAL_SECONDS):
                with pending_approvals_lock:
                    approved = pending_approvals[request_id]["approved"]
                if approved:
                    return True, None
                return False, "Kullanıcı komutu reddetti."
            elapsed += APPROVAL_POLL_INTERVAL_SECONDS

        return False, "Onay isteği zaman aşımına uğradı."
    finally:
        # Kullanıcı hiç yanıt vermese bile (timeout/interrupt) pending_approvals'ta
        # kalıp sızıntı yapmaması için garanti temizlik.
        with pending_approvals_lock:
            pending_approvals.pop(request_id, None)


def run_terminal_command(command):
    if not _is_whitelisted(command):
        approved, reason = _await_approval(command)
        if not approved:
            return f"Komut çalıştırılmadı: {reason}"

    try:
        result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True, timeout=15)
        if result.returncode == 0: return f"Command executed successfully: {result.stdout.strip()}"
        else: return f"Command failed: {result.stderr.strip()}"
    except Exception as e:
        return f"Error executing command: {e}"

def press_keys(keys):
    try:
        keys_list = keys.split('+')
        if len(keys_list) == 1: pyautogui.press(keys_list[0].strip())
        else: pyautogui.hotkey(*[k.strip() for k in keys_list])
        return f"Successfully pressed: {keys}"
    except Exception as e: return f"Error pressing keys: {e}"

def type_text(text):
    try:
        pyautogui.write(text, interval=0.05)
        return f"Successfully typed: {text}"
    except Exception as e: return f"Error typing text: {e}"

TOOL_MAP = {
    "open_website": open_website,
    "search_youtube": search_youtube,
    "open_application": open_application,
    "close_application": close_application,
    "get_time_and_date": get_time_and_date,
    "run_terminal_command": run_terminal_command,
    "press_keys": press_keys,
    "type_text": type_text,
    "search_files": search_files,
    "move_file": move_file,
    "copy_file": copy_file
}

GEMINI_TOOLS = [{
    "functionDeclarations": [
        {"name": "open_website", "description": "Opens a website URL.", "parameters": {"type": "OBJECT", "properties": {"url": {"type": "STRING"}}, "required": ["url"]}},
        {"name": "search_youtube", "description": "Searches YouTube.", "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]}},
        {"name": "open_application", "description": "Opens a local Windows application.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING"}}, "required": ["app_name"]}},
        {"name": "close_application", "description": "Force-closes a running local Windows application/process by name (e.g. 'notepad', 'spotify', 'chrome'). Use this when the user asks to close, quit, kill, or stop a specific app. Cannot close critical system processes (explorer, services, lsass, etc.) — those requests are always refused.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING", "description": "The process/app name, with or without the .exe extension (e.g. 'notepad' or 'notepad.exe')."}}, "required": ["app_name"]}},
        {"name": "get_time_and_date", "description": "Gets current time.", "parameters": {"type": "OBJECT"}},
        {"name": "run_terminal_command", "description": "Runs a PowerShell command.", "parameters": {"type": "OBJECT", "properties": {"command": {"type": "STRING"}}, "required": ["command"]}},
        {"name": "press_keys", "description": "Simulates keyboard presses (e.g. ctrl+c).", "parameters": {"type": "OBJECT", "properties": {"keys": {"type": "STRING"}}, "required": ["keys"]}},
        {"name": "type_text", "description": "Simulates typing.", "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}}, "required": ["text"]}},
        {"name": "search_files", "description": "Searches for files by name within the user's standard folders (Desktop, Documents, Downloads, Pictures). Cannot search outside these folders.", "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING", "description": "Substring to match against file names."}, "folder": {"type": "STRING", "description": "Optional: limit the search to one folder ('masaustu', 'belgeler', 'indirilenler', 'resimler' — Turkish characters are normalized automatically). If omitted, searches all four."}}, "required": ["query"]}},
        {"name": "move_file", "description": "Moves a file between the user's standard folders (Desktop, Documents, Downloads, Pictures). Asks for confirmation if the destination already has a file with the same name.", "parameters": {"type": "OBJECT", "properties": {"source": {"type": "STRING"}, "destination": {"type": "STRING"}}, "required": ["source", "destination"]}},
        {"name": "copy_file", "description": "Copies a file between the user's standard folders (Desktop, Documents, Downloads, Pictures). Asks for confirmation if the destination already has a file with the same name.", "parameters": {"type": "OBJECT", "properties": {"source": {"type": "STRING"}, "destination": {"type": "STRING"}}, "required": ["source", "destination"]}}
    ]
}]
