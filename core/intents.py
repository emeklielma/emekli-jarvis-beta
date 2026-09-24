"""
Fast-path intent detection for voice commands that should not depend on the LLM
deciding to call a tool (faster and works even when Gemini is rate limited).
"""

import re
from typing import Optional, Dict

# "jarvis," / "hadi" gibi başlangıç kelimeleri
_PREFIX = r"^(?:(?:hey\s+)?jarvis\s*[,.!]?\s+)?(?:hadi\s+|haydi\s+|tamam\s+|let'?s\s+)?"

_TR_PROJECT_SUFFIX = r"proje(?:si|sine|sini|sinde|ye|yi|me|mi|mize|mizi|ne)?"
_TR_CONTINUE_VERB = r"(?:devam|geri\s+d[öo]n|d[öo]n|a[çc]|ba[şs]la|[çc]al[ıi][şs])"

_CONTINUE_PATTERNS = [
    # "emekli jarvis projesine devam edelim", "jarvis projeye devam"
    re.compile(_PREFIX + r"(?P<name>.+?)\s+" + _TR_PROJECT_SUFFIX + r"\s+" + _TR_CONTINUE_VERB),
    # "projeye devam edelim" (isimsiz -> son proje)
    re.compile(_PREFIX + _TR_PROJECT_SUFFIX + r"\s+" + _TR_CONTINUE_VERB),
    # "continue (with) the jarvis project", "let's work on the jarvis project"
    re.compile(_PREFIX + r"(?:continue|resume|work\s+on|get\s+back\s+to)\s+(?:with\s+|on\s+)?(?:the\s+|my\s+|our\s+)?(?P<name>.+?)\s+project\b"),
]

_NEW_PATTERNS = [
    # "hava durumu adında bir uygulama yapacağım", "yeni bir uygulama yapalım", "uygulama yapıcam"
    re.compile(_PREFIX + r"(?:(?P<name>.+?)\s+(?:ad[ıi]nda|adl[ıi]|isimli|diye)\s+)?(?:yeni\s+)?(?:bir\s+)?"
               r"(?:uygulama|app|aplikasyon|site|web\s*sitesi|oyun|proje)\s+"
               r"(?:yap|geli[şs]tir|kodla|yaz|olu[şs]tur|ba[şs]lat)"),
    # "claude'u aç", "claude aç", "open claude"
    re.compile(_PREFIX + r"claude\S*\s+(?:a[çc]|ba[şs]lat)"),
    re.compile(_PREFIX + r"(?:open|launch|start)\s+claude\b"),
    # "i'm going to build an app", "let's make a new app"
    re.compile(_PREFIX + r"(?:i'?m\s+going\s+to\s+|i\s+want\s+to\s+|i'?ll\s+)?(?:build|make|create|code)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:app|application|website|game)\b"),
]


_FILLER_WORDS = {"hadi", "haydi", "tamam", "hey", "bu", "şu", "o", "bizim", "benim", "the", "my", "our"}


def _project_name(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    words = raw.strip(" ,.'").split()
    # Baştaki "jarvis" hitap olabilir; ama proje adı sadece "jarvis" ise kalmalı
    while len(words) > 1 and (words[0] in _FILLER_WORDS or words[0] == "jarvis"):
        words.pop(0)
    if len(words) == 1 and words[0] in _FILLER_WORDS:
        return None
    return " ".join(words) or None


def _clean(text: str) -> str:
    # Python'da "İ".lower() -> "i̇" (noktalı i); düz i'ye çevir
    text = text.lower().replace("i̇", "i").strip()
    return re.sub(r"\s+", " ", text)


def match_claude_intent(text: str) -> Optional[Dict[str, Optional[str]]]:
    """Returns {"mode": "new"|"continue", "project_name": str|None} or None."""
    if not text:
        return None
    t = _clean(text)
    for pattern in _CONTINUE_PATTERNS:
        m = pattern.search(t)
        if m:
            return {"mode": "continue", "project_name": _project_name(m.groupdict().get("name"))}
    for pattern in _NEW_PATTERNS:
        m = pattern.search(t)
        if m:
            return {"mode": "new", "project_name": _project_name(m.groupdict().get("name"))}
    return None


_CALL_ME_PATTERNS = [
    # "beni ara", "telefonumu ara", "beni telefondan arar mısın"
    re.compile(_PREFIX + r"(?:beni|telefonumu|numaram[ıi])\s+(?:telefondan\s+|şimdi\s+|hemen\s+)?ara(?:r\s*m[ıi]s[ıi]n|y[ıi]n|\b)"),
    re.compile(_PREFIX + r"(?:please\s+)?call\s+(?:me|my\s+phone)\b"),
]


def match_call_me_intent(text: str) -> bool:
    if not text:
        return False
    t = _clean(text)
    return any(p.search(t) for p in _CALL_ME_PATTERNS)
