from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


SAFE_API_BASE = "https://www.moltbook.com/api/v1"


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    api_base: str
    dry_run: bool
    bot_name: str
    default_submolt: str
    state_path: Path
    autonomy_interval_seconds: int
    max_actions_per_heartbeat: int
    auto_reply_dms: bool
    auto_approve_dm_requests: bool


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(value: str | None, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        number = int(value) if value is not None else default
    except (TypeError, ValueError):
        number = default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _env_first(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def load_settings(env_file: str | None = ".env") -> Settings:
    if load_dotenv and env_file:
        load_dotenv(env_file)

    api_base = os.getenv("MOLTBOOK_API_BASE", SAFE_API_BASE).rstrip("/")
    if api_base != SAFE_API_BASE:
        raise ValueError(
            "MOLTBOOK_API_BASE precisa ser exatamente "
            f"{SAFE_API_BASE!r}. O bot não envia API key para outro domínio."
        )

    return Settings(
        api_key=os.getenv("MOLTBOOK_API_KEY") or None,
        api_base=api_base,
        dry_run=_as_bool(os.getenv("MOLTBOOK_DRY_RUN"), default=True),
        bot_name=os.getenv("BOT_NAME", "Gingeredspi4395"),
        default_submolt=os.getenv("BOT_SUBMOLT", "general"),
        state_path=Path(os.getenv("BOT_STATE_PATH", ".gingeredspi4395_moltbook_state.json")),
        autonomy_interval_seconds=_as_int(_env_first("GINGER_AUTONOMY_INTERVAL_SECONDS", "TOM_AUTONOMY_INTERVAL_SECONDS"), 14400, minimum=60),
        max_actions_per_heartbeat=_as_int(_env_first("GINGER_MAX_ACTIONS_PER_HEARTBEAT", "TOM_MAX_ACTIONS_PER_HEARTBEAT"), 3, minimum=1, maximum=10),
        auto_reply_dms=_as_bool(_env_first("GINGER_AUTO_REPLY_DMS", "TOM_AUTO_REPLY_DMS"), default=True),
        auto_approve_dm_requests=_as_bool(_env_first("GINGER_AUTO_APPROVE_DM_REQUESTS", "TOM_AUTO_APPROVE_DM_REQUESTS"), default=False),
    )
