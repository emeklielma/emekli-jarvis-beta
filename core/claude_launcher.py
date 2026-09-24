"""
Claude launcher: "uygulama yapacağım" / "<isim> projesine devam edelim" gibi
komutlarda Claude'u açar.

Öncelik sırası (JARVIS_CLAUDE_MODE ile değiştirilebilir: auto | code | desktop | web):
  1. Claude Code (CLI, `claude`) -> proje klasöründe yeni bir terminal penceresinde
  2. Claude masaüstü uygulaması
  3. claude.ai (tarayıcı)

Proje klasörleri JARVIS_PROJECTS_DIRS içindeki klasörlerde aranır (os.pathsep ile
ayrılmış liste; Windows'ta ';'). Verilmezse Masaüstü, Belgeler, Projeler vb. taranır.
"""

import os
import re
import json
import shutil
import subprocess
import webbrowser
from typing import Optional, List, Tuple

from rapidfuzz import fuzz

HOME = os.path.expanduser("~")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STATE_FILE = os.path.join(DATA_DIR, "claude_projects.json")

DEFAULT_PROJECT_ROOTS = [
    os.path.join(HOME, "Projeler"),
    os.path.join(HOME, "Projects"),
    os.path.join(HOME, "Desktop"),
    os.path.join(HOME, "Desktop", "Projeler"),
    os.path.join(HOME, "Desktop", "Projects"),
    os.path.join(HOME, "Documents"),
    os.path.join(HOME, "Documents", "Projeler"),
    os.path.join(HOME, "Documents", "GitHub"),
    os.path.join(HOME, "source", "repos"),
    HOME,
]

_SKIP_DIRS = {"node_modules", "venv", ".venv", "__pycache__", "appdata", "application data",
              "my music", "my pictures", "my videos", "onedrive", "downloads", "music",
              "pictures", "videos", "favorites", "contacts", "links", "saved games", "searches"}

_TR_MAP = str.maketrans({"ı": "i", "İ": "i", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u",
                         "ş": "s", "Ş": "s", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"})

MATCH_THRESHOLD = 75


def _compact(text: str) -> str:
    """'Emekli-Jarvis Beta' -> 'emeklijarvisbeta' (Türkçe karakterler sadeleştirilir)."""
    text = text.translate(_TR_MAP).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _slug(text: str) -> str:
    text = text.translate(_TR_MAP).lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "yeni-uygulama"


def project_roots() -> List[str]:
    env = os.getenv("JARVIS_PROJECTS_DIRS", "").strip()
    roots = [os.path.expanduser(p.strip()) for p in env.split(os.pathsep) if p.strip()] if env else DEFAULT_PROJECT_ROOTS
    return [r for r in dict.fromkeys(roots) if os.path.isdir(r)]


def new_projects_root() -> str:
    env = os.getenv("JARVIS_NEW_PROJECTS_DIR", "").strip()
    if env:
        return os.path.expanduser(env)
    roots = project_roots()
    return roots[0] if roots else os.path.join(HOME, "Projeler")


def _candidate_dirs() -> List[str]:
    dirs = []
    for root in project_roots():
        try:
            for entry in os.scandir(root):
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if entry.name.startswith(".") or entry.name.lower() in _SKIP_DIRS:
                    continue
                dirs.append(entry.path)
        except OSError:
            continue
    return list(dict.fromkeys(dirs))


def find_project(name: str) -> Optional[str]:
    """Returns the best matching project folder for a spoken project name."""
    query = _compact(name)
    if not query:
        return None
    best: Tuple[float, Optional[str]] = (0, None)
    for path in _candidate_dirs():
        folder = _compact(os.path.basename(path))
        if not folder:
            continue
        if folder == query:
            return path
        score = max(fuzz.ratio(query, folder), fuzz.partial_ratio(query, folder) - 5)
        # 'jarvis' -> 'emeklijarvisbeta' gibi alt dize eşleşmesi, çok kısa sorgular hariç
        if len(query) >= 4 and query in folder:
            score = max(score, 90)
        if score > best[0]:
            best = (score, path)
    return best[1] if best[0] >= MATCH_THRESHOLD else None


def _load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(data: dict):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CLAUDE] Could not save state: {e}")


def _remember_project(path: str):
    data = _load_state()
    data["last_project"] = path
    _save_state(data)


def _last_project() -> Optional[str]:
    path = _load_state().get("last_project")
    return path if path and os.path.isdir(path) else None


# ---------------------------------------------------------
# LAUNCHERS
# ---------------------------------------------------------

def _claude_cli() -> Optional[str]:
    return shutil.which("claude")


def _launch_claude_code(cwd: str, resume: bool) -> bool:
    cli = _claude_cli()
    if not cli:
        return False
    # --continue son konuşmayı sürdürür; o klasörde hiç konuşma yoksa normal açılır.
    command = "claude --continue || claude" if resume else "claude"
    try:
        if os.name == "nt":
            subprocess.Popen(["cmd", "/k", command], cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(["sh", "-c", command], cwd=cwd)
        return True
    except Exception as e:
        print(f"[CLAUDE] Claude Code could not be started: {e}")
        return False


def _launch_claude_desktop() -> bool:
    try:
        from core import app_launcher
        info = app_launcher.resolve_app_target("claude")
        if info and "claude" in str(info.get("name", "")).lower():
            return app_launcher.launch_target(info.get("target"))
    except Exception as e:
        print(f"[CLAUDE] Desktop app lookup failed: {e}")
    return False


def _open_folder(path: str):
    try:
        if os.name == "nt":
            os.startfile(path)
    except Exception:
        pass


def _launch(cwd: Optional[str], resume: bool) -> str:
    """Tries the configured launch methods; returns which one worked ('code'/'desktop'/'web')."""
    mode = os.getenv("JARVIS_CLAUDE_MODE", "auto").strip().lower()
    order = {"code": ["code"], "desktop": ["desktop"], "web": ["web"]}.get(mode, ["code", "desktop", "web"])
    for method in order:
        if method == "code" and _launch_claude_code(cwd or new_projects_root(), resume):
            return "code"
        if method == "desktop" and _launch_claude_desktop():
            if cwd:
                _open_folder(cwd)
            return "desktop"
        if method == "web":
            webbrowser.open("https://claude.ai/new")
            if cwd:
                _open_folder(cwd)
            return "web"
    # Only a single, unavailable method was configured -> fall back to the web.
    webbrowser.open("https://claude.ai/new")
    return "web"


_METHOD_NAMES = {"code": "Claude Code", "desktop": "Claude uygulaması", "web": "claude.ai"}


def open_claude(mode: str = "new", project_name: Optional[str] = None) -> str:
    """mode: 'new' (yeni uygulama/proje) or 'continue' (mevcut projeye devam)."""
    project_name = (project_name or "").strip() or None

    if mode == "continue":
        path = find_project(project_name) if project_name else _last_project()
        if not path:
            if project_name:
                print(f"[CLAUDE] '{project_name}' not found in: {', '.join(project_roots()) or '-'} "
                      f"(set JARVIS_PROJECTS_DIRS in .env to add folders)")
                return f"'{project_name}' adında bir proje klasörü bulamadım."
            return "Hangi projeye devam edelim? Proje adını söyler misiniz?"
        method = _launch(path, resume=True)
        _remember_project(path)
        return f"{_METHOD_NAMES[method]} açıldı, {os.path.basename(path)} projesine devam ediyoruz."

    # mode == "new"
    if project_name:
        existing = find_project(project_name)
        if existing and _compact(os.path.basename(existing)) == _compact(project_name):
            method = _launch(existing, resume=True)
            _remember_project(existing)
            return f"{os.path.basename(existing)} zaten var; {_METHOD_NAMES[method]} ile o projeyi açtım."
        path = os.path.join(new_projects_root(), _slug(project_name))
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            return f"Proje klasörü oluşturulamadı: {e}"
        method = _launch(path, resume=False)
        _remember_project(path)
        return f"{_METHOD_NAMES[method]} açıldı. Yeni proje klasörü: {path}"

    method = _launch(None, resume=False)
    return f"{_METHOD_NAMES[method]} açıldı, yeni uygulamaya hazırız."
