from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BotState:
    last_post_at: float = 0.0
    last_comment_at: float = 0.0
    comment_day: str = ""
    comments_today: int = 0
    field_note_number: int = 1
    seen_post_ids: list[str] = field(default_factory=list)
    processed_signal_ids: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "BotState":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            allowed = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**allowed)
        except Exception:
            return cls()

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.__dict__, indent=2, ensure_ascii=False), encoding="utf-8")

    def can_post(self, cooldown_seconds: int = 30 * 60) -> tuple[bool, str]:
        delta = time.time() - self.last_post_at
        if delta < cooldown_seconds:
            remaining = int(cooldown_seconds - delta)
            return False, f"post cooldown ativo: aguarde {remaining}s"
        return True, "ok"

    def can_comment(self, cooldown_seconds: int = 20, daily_cap: int = 50) -> tuple[bool, str]:
        today = time.strftime("%Y-%m-%d")
        if self.comment_day != today:
            self.comment_day = today
            self.comments_today = 0

        if self.comments_today >= daily_cap:
            return False, "limite diário de comentários atingido"

        delta = time.time() - self.last_comment_at
        if delta < cooldown_seconds:
            remaining = int(cooldown_seconds - delta)
            return False, f"comment cooldown ativo: aguarde {remaining}s"
        return True, "ok"

    def mark_posted(self) -> None:
        self.last_post_at = time.time()
        self.field_note_number += 1

    def mark_commented(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if self.comment_day != today:
            self.comment_day = today
            self.comments_today = 0
        self.comments_today += 1
        self.last_comment_at = time.time()

    def remember_seen_post(self, post_id: str, max_seen: int = 250) -> None:
        if not post_id or post_id in self.seen_post_ids:
            return
        self.seen_post_ids.append(post_id)
        self.seen_post_ids = self.seen_post_ids[-max_seen:]

    def was_processed(self, signal_id: str) -> bool:
        return signal_id in self.processed_signal_ids

    def remember_processed(self, signal_id: str, max_seen: int = 500) -> None:
        if not signal_id or signal_id in self.processed_signal_ids:
            return
        self.processed_signal_ids.append(signal_id)
        self.processed_signal_ids = self.processed_signal_ids[-max_seen:]
