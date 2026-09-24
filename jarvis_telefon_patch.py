"""
Adds "call me" / "beni ara" to a Jarvis whose backend has a fast_path.py with a
`match()` fast path (the Masaüstü\\jarvis project): typing or saying it makes
Jarvis ask Jarvis Telefon (jarvis_telefon.py, http://127.0.0.1:8431/call) to
ring the owner's phone.

    python jarvis_telefon_patch.py            (run in the Jarvis folder)

Makes backend\\fast_path.py.bak first; running it twice changes nothing.
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "backend", "fast_path.py")
MARKER = "_PHONE_CONTROL_URL"

IMPORTS_OLD = "import random\nimport re\nfrom datetime import datetime\n"
IMPORTS_NEW = "import json\nimport random\nimport re\nimport urllib.request\nfrom datetime import datetime\n"

BLOCK_ANCHOR = "_TR_FOLD = str.maketrans("
BLOCK = '''# "call me" / "beni ara": Jarvis Telefon (jarvis_telefon.py, Linphone) rings the
# owner's phone. It listens on this local control address only.
_PHONE_CONTROL_URL = "http://127.0.0.1:8431/call"
_CALL_ME_RE = re.compile(
    r"^(?:(?:hey )?jarvis )?(?:please |lutfen )?(?:can you |could you )?"
    r"(?:call me|call my phone|give me a call|ring me|phone me|"
    r"beni (?:hemen |simdi )?ara(?:r ?misin|yin)?|"
    r"telefonumu (?:hemen )?ara(?:r ?misin|yin)?)"
    r"(?: please| lutfen| jarvis| sir| now| hemen)*$"
)


def _call_me() -> dict:
    """Asks Jarvis Telefon to call the owner; replies without the model."""
    tr = _lang() == "tr"
    try:
        req = urllib.request.Request(
            _PHONE_CONTROL_URL, data=b"{}",
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            result = json.loads(resp.read().decode("utf-8")).get("result", "")
    except Exception:  # noqa: BLE001
        return _plan(None, {}, (
            "Telefon hattı kapalı, efendim. Önce Jarvis-Telefon.bat'ı açın."
            if tr else
            "The phone line is offline, sir. Please start Jarvis-Telefon.bat first."
        ))
    if "arıyorum" in result:
        reply = "Sizi arıyorum, efendim." if tr else "Calling your phone now, sir."
    elif "Zaten" in result:
        reply = "Zaten görüşmedeyiz, efendim." if tr else "We're already on a call, sir."
    else:
        reply = (
            "Telefon hattı henüz bağlanmadı, efendim." if tr else
            "The phone line isn't connected yet, sir."
        )
    return _plan(None, {}, reply)


'''

MATCH_OLD = '''    tokens = low.split()
    if not tokens:
        return None

'''
MATCH_NEW = '''    tokens = low.split()
    if not tokens:
        return None

    # 0. "call me" / "beni ara" -> ring the owner's phone via Jarvis Telefon
    if _CALL_ME_RE.match(_fold(low)):
        return _call_me()

'''


def main() -> int:
    if not os.path.exists(TARGET):
        print(f"[HATA] {TARGET} bulunamadı. Bu dosyayı Jarvis klasörüne (backend'in yanına) koyun.")
        return 1
    with open(TARGET, encoding="utf-8") as f:     # universal newlines: CRLF is fine
        src = f.read()
    if MARKER in src:
        print("[TAMAM] fast_path.py zaten güncel, değişiklik yapılmadı.")
        return 0
    missing = [name for name, text in (("importlar", IMPORTS_OLD), ("_TR_FOLD", BLOCK_ANCHOR), ("match()", MATCH_OLD))
               if text not in src]
    if missing:
        print(f"[HATA] fast_path.py beklenenden farklı ({', '.join(missing)} bulunamadı). Dosyaya dokunulmadı.")
        return 1
    new = src.replace(IMPORTS_OLD, IMPORTS_NEW, 1)
    new = new.replace(BLOCK_ANCHOR, BLOCK + BLOCK_ANCHOR, 1)
    new = new.replace(MATCH_OLD, MATCH_NEW, 1)
    compile(new, TARGET, "exec")                     # never write a file that doesn't parse
    shutil.copy2(TARGET, TARGET + ".bak")
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(new)
    print("[TAMAM] fast_path.py güncellendi (yedek: backend\\fast_path.py.bak).")
    print("Jarvis'i kapatıp yeniden açın; sonra mesaj kutusuna 'call me' yazın.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
