from __future__ import annotations

import re
from typing import Any

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
}


def _compact_text(text: str) -> str:
    # Moltbook challenges may be visually noisy: alternating caps and punctuation.
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _numbers_from_digits(text: str) -> list[float]:
    return [float(match) for match in re.findall(r"\d+(?:\.\d+)?", text)]


def _numbers_from_words(text: str) -> list[float]:
    compact = _compact_text(text)
    found: list[tuple[int, int, float]] = []

    # Prefer longer words first so "seventeen" wins before "seven"/"ten".
    for word, value in sorted(NUMBER_WORDS.items(), key=lambda item: len(item[0]), reverse=True):
        for match in re.finditer(re.escape(word), compact):
            found.append((match.start(), match.end(), float(value)))

    found.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    chosen: list[tuple[int, int, float]] = []
    occupied: list[tuple[int, int]] = []
    for start, end, value in found:
        if any(not (end <= a or start >= b) for a, b in occupied):
            continue
        chosen.append((start, end, value))
        occupied.append((start, end))

    chosen.sort(key=lambda item: item[0])
    return [value for _, _, value in chosen]


def solve_verification_challenge(challenge_text: str) -> str | None:
    """Solve simple Moltbook arithmetic challenges.

    This intentionally handles only low-risk arithmetic checks like force totals.
    It returns a number formatted with two decimals, or None when unsure.
    """
    lower = challenge_text.lower()
    numbers = _numbers_from_digits(challenge_text) or _numbers_from_words(challenge_text)
    if not numbers:
        return None

    # The platform's public challenges usually ask for a total after forces are added.
    if any(token in lower for token in ["total", "sum", "add", "adds", "combined", "together", "+"]):
        return f"{sum(numbers):.2f}"

    # Conservative fallback: if exactly two force values are present, treat it as total force.
    if "force" in lower or "newton" in lower or len(numbers) == 2:
        return f"{sum(numbers):.2f}"

    return None


def extract_verification(payload: dict[str, Any]) -> tuple[str, str] | None:
    """Return (verification_code, challenge_text) from Moltbook payloads when present."""
    if not isinstance(payload, dict):
        return None

    candidates = [payload]
    for key in ("post", "comment", "content", "result"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append(value)

    for candidate in candidates:
        verification = candidate.get("verification")
        if isinstance(verification, dict):
            code = verification.get("verification_code") or verification.get("code")
            challenge = verification.get("challenge_text") or verification.get("challenge")
            if code and challenge:
                return str(code), str(challenge)
    return None
