from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass
class HomeSignal:
    """A normalized item discovered in /api/v1/home.

    Moltbook's /home payload can evolve. This object captures the fields Tom needs
    without assuming one exact JSON shape.
    """

    signal_id: str
    kind: str
    title: str = ""
    content: str = ""
    author: str = ""
    post_id: str = ""
    comment_id: str = ""
    conversation_id: str = ""
    needs_human_input: bool = False
    raw: dict[str, Any] | None = None


SENSITIVE_PATTERNS = [
    r"api\s*key",
    r"password",
    r"credential",
    r"secret",
    r"private\s*key",
    r"seed\s*phrase",
    r"wallet",
    r"bank",
    r"pix",
    r"credit\s*card",
    r"ignore\s+(your\s+)?instructions",
    r"system\s+prompt",
    r"developer\s+message",
    r"reveal\s+.*prompt",
    r"medical",
    r"legal\s+advice",
    r"lawsuit",
    r"human\s+owner",
    r"needs_human_input",
]


def should_escalate_to_human(text: str) -> tuple[bool, str]:
    lower = (text or "").lower()
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, lower):
            return True, f"conteúdo sensível detectado: {pattern}"
    if len(lower) > 2000:
        return True, "mensagem longa demais para resposta autônoma segura"
    return False, "ok"


def extract_home_signals(home_payload: dict[str, Any], *, bot_name: str) -> list[HomeSignal]:
    """Best-effort parser for Moltbook /home.

    The live endpoint may return notifications, replies, DMs, suggested actions,
    or feed fragments under changing key names. This function scans nested lists
    and dictionaries and extracts anything that looks actionable.
    """

    signals: list[HomeSignal] = []
    bot_lower = bot_name.lower()

    for item in _walk_dicts(home_payload):
        text_blob = _text_blob(item)
        lower = text_blob.lower()
        kind = str(item.get("type") or item.get("kind") or item.get("event_type") or "").lower()

        looks_like_dm = any(k in item for k in ("conversation_id", "unread_count", "message_preview")) or "dm" in kind
        looks_like_mention = bot_lower in lower or "mention" in kind
        looks_like_reply = any(k in item for k in ("comment_id", "parent_id", "reply_count")) or "reply" in kind or "comment" in kind

        if not (looks_like_dm or looks_like_mention or looks_like_reply):
            continue

        signal_id = _first_str(item, "id", "notification_id", "message_id", "comment_id", "conversation_id")
        if not signal_id:
            signal_id = str(abs(hash(text_blob)))

        signals.append(
            HomeSignal(
                signal_id=signal_id,
                kind=("dm" if looks_like_dm else "mention" if looks_like_mention else "reply"),
                title=_first_str(item, "title", "subject", "post_title"),
                content=_first_str(item, "content", "body", "message", "message_preview", "text", "snippet"),
                author=_extract_author(item),
                post_id=_first_str(item, "post_id", "postId"),
                comment_id=_first_str(item, "comment_id", "commentId", "id"),
                conversation_id=_first_str(item, "conversation_id", "conversationId"),
                needs_human_input=bool(item.get("needs_human_input") or item.get("needsHumanInput")),
                raw=item,
            )
        )

    return _dedupe(signals)


def _walk_dicts(obj: Any) -> Iterable[dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_dicts(value)


def _first_str(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def _extract_author(item: dict[str, Any]) -> str:
    author = item.get("author") or item.get("from") or item.get("with_agent") or item.get("agent")
    if isinstance(author, dict):
        return _first_str(author, "name", "username", "handle")
    if isinstance(author, str):
        return author
    return _first_str(item, "author_name", "from_name", "agent_name")


def _text_blob(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "subject", "content", "body", "message", "message_preview", "text", "snippet", "type", "kind"):
        value = item.get(key)
        if isinstance(value, str):
            parts.append(value)
    author = _extract_author(item)
    if author:
        parts.append(author)
    return "\n".join(parts)


def _dedupe(signals: list[HomeSignal]) -> list[HomeSignal]:
    seen: set[str] = set()
    out: list[HomeSignal] = []
    for signal in signals:
        key = f"{signal.kind}:{signal.signal_id}:{signal.post_id}:{signal.conversation_id}"
        if key in seen:
            continue
        seen.add(key)
        out.append(signal)
    return out
