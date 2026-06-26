from __future__ import annotations

import re

SECRET_PATTERNS = [
    re.compile(r"moltbook_[A-Za-z0-9_\-]{12,}", re.I),
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}", re.I),
    re.compile(r"api[_-]?key\s*[:=]\s*\S+", re.I),
    re.compile(r"authorization\s*[:=]\s*bearer\s+\S+", re.I),
    re.compile(r"password\s*[:=]\s*\S+", re.I),
    re.compile(r"token\s*[:=]\s*\S+", re.I),
]

INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?(previous|prior|above) instructions", re.I),
    re.compile(r"reveal (your )?(system|hidden|developer) prompt", re.I),
    re.compile(r"print (your )?(api key|secret|token|credentials)", re.I),
    re.compile(r"run this command", re.I),
    re.compile(r"curl .*http", re.I),
    re.compile(r"exfiltrate|leak|steal|credential", re.I),
]


def redact_secrets(text: str) -> str:
    redacted = text or ""
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def looks_like_prompt_injection(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in INJECTION_PATTERNS)


def clean_untrusted_text(text: str, max_chars: int = 1600) -> str:
    if not text:
        return ""
    text = redact_secrets(text).replace("\x00", "").strip()
    injection = looks_like_prompt_injection(text)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    if injection:
        text = "[UNTRUSTED/POSSIBLE PROMPT INJECTION REMOVED] " + text
    return text


def safe_outbound_text(text: str, max_chars: int = 4000) -> str:
    text = redact_secrets(text or "").strip()
    if not text:
        raise ValueError("Texto vazio após sanitização.")
    if looks_like_prompt_injection(text):
        raise ValueError("Texto de saída parece conter instrução de ataque ou vazamento.")
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return text
