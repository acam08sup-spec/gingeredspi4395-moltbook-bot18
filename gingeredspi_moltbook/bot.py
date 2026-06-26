from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .autonomy import HomeSignal, extract_home_signals, should_escalate_to_human
from .config import Settings
from .moltbook_client import MoltbookClient, MoltbookError
from .moltbook_context import best_comment_target
from .persona import DESCRIPTION, FIRST_POST_CONTENT, FIRST_POST_TITLE
from .state import BotState
from .verification import extract_verification, solve_verification_challenge
from .writer import GingerWriter


@dataclass
class GingerBot:
    settings: Settings
    client: MoltbookClient
    state: BotState
    writer: GingerWriter

    @classmethod
    def from_settings(cls, settings: Settings) -> "GingerBot":
        return cls(
            settings=settings,
            client=MoltbookClient(api_key=settings.api_key, api_base=settings.api_base),
            state=BotState.load(settings.state_path),
            writer=GingerWriter(),
        )

    def save(self) -> None:
        self.state.save(self.settings.state_path)

    def register(self) -> dict[str, Any]:
        return self.client.register_agent(self.settings.bot_name, DESCRIPTION)

    def status(self) -> dict[str, Any]:
        return self.client.status()

    def home(self) -> dict[str, Any]:
        return self.client.home()

    def first_post(self) -> dict[str, Any]:
        can_post, reason = self.state.can_post()
        if not can_post:
            return {"dry_run": self.settings.dry_run, "skipped": True, "reason": reason}

        payload = {
            "submolt": self.settings.default_submolt,
            "title": FIRST_POST_TITLE,
            "content": FIRST_POST_CONTENT,
        }
        if self.settings.dry_run:
            return {"dry_run": True, "would_post": payload}

        result = self.client.create_post(**payload)
        verified = self._auto_verify(result)
        if verified:
            result["auto_verification"] = verified
        self.state.mark_posted()
        self.save()
        return result

    def draft_field_note(self) -> dict[str, Any]:
        draft = self.writer.field_note(self.state.field_note_number)
        return {
            "submolt": self.settings.default_submolt,
            "title": draft.title,
            "content": draft.content,
        }

    def post_field_note(self) -> dict[str, Any]:
        can_post, reason = self.state.can_post()
        payload = self.draft_field_note()
        if not can_post:
            return {"dry_run": self.settings.dry_run, "skipped": True, "reason": reason, "draft": payload}
        if self.settings.dry_run:
            return {"dry_run": True, "would_post": payload}

        result = self.client.create_post(**payload)
        verified = self._auto_verify(result)
        if verified:
            result["auto_verification"] = verified
        self.state.mark_posted()
        self.save()
        return result

    def heartbeat(
        self,
        *,
        allow_post: bool = False,
        allow_comment: bool = False,
        allow_dm: bool = False,
        allow_home_reply: bool = False,
    ) -> dict[str, Any]:
        """Check Moltbook and optionally act.

        Conservative by default. With flags enabled, Gingeredspi4395 can:
        - answer routine DMs/conversation signals;
        - reply to mentions/comments found in /home when possible;
        - comment on one relevant feed post;
        - post a field note if cooldown allows.
        """
        report: dict[str, Any] = {
            "dry_run": self.settings.dry_run,
            "status": None,
            "home": None,
            "dm_check": None,
            "posts_seen": 0,
            "actions": [],
            "needs_human": [],
            "warnings": [],
            "errors": [],
        }

        actions_taken = 0

        try:
            report["status"] = self.client.status()
        except MoltbookError as exc:
            report["errors"].append(f"status: {exc}")

        home_signals: list[HomeSignal] = []
        try:
            home_payload = self.client.home()
            report["home"] = {"success": home_payload.get("success", True), "keys": list(home_payload.keys())}
            home_signals = extract_home_signals(home_payload, bot_name=self.settings.bot_name)
            report["home"]["signals_seen"] = len(home_signals)
        except MoltbookError as exc:
            report["warnings"].append(f"home indisponível: {exc}")

        try:
            report["dm_check"] = self.client.check_dms()
        except MoltbookError as exc:
            # The official docs mention this endpoint, but the live platform may return 404.
            # Do not treat that as fatal; /home is the fallback.
            report["warnings"].append(f"dm_check indisponível; usando /home como fallback: {exc}")

        if allow_dm and self.settings.auto_reply_dms and actions_taken < self.settings.max_actions_per_heartbeat:
            actions_taken += self._handle_dms(report, home_signals, actions_taken)

        if allow_home_reply and home_signals and actions_taken < self.settings.max_actions_per_heartbeat:
            actions_taken += self._handle_home_signals(report, home_signals, actions_taken)

        posts: list[dict[str, Any]] = []
        try:
            raw = self.client.list_posts(sort="new", limit=10)
            posts = self._extract_posts(raw)
            report["posts_seen"] = len(posts)
            for post in posts:
                post_id = str(post.get("id") or "")
                if post_id:
                    self.state.remember_seen_post(post_id)
        except MoltbookError as exc:
            report["errors"].append(f"list_posts: {exc}")

        if allow_comment and posts and actions_taken < self.settings.max_actions_per_heartbeat:
            can_comment, reason = self.state.can_comment()
            if can_comment:
                target = best_comment_target(posts, bot_name=self.settings.bot_name)
                if target is None:
                    report["actions"].append({"comment_skipped": "nenhum post adequado para comentar"})
                else:
                    post_id = target.post_id
                    comment = self.writer.comment_on_post(target)
                    if self.settings.dry_run:
                        report["actions"].append({"would_comment_on": post_id, "content": comment})
                        actions_taken += 1
                    elif post_id:
                        try:
                            result = self.client.create_comment(post_id=post_id, content=comment)
                            verified = self._auto_verify(result)
                            if verified:
                                result["auto_verification"] = verified
                            self.state.mark_commented()
                            actions_taken += 1
                            report["actions"].append({"commented_on": post_id, "result": result})
                        except MoltbookError as exc:
                            report["errors"].append(f"comment: {exc}")
            else:
                report["actions"].append({"comment_skipped": reason})

        if allow_post and actions_taken < self.settings.max_actions_per_heartbeat:
            report["actions"].append({"field_note": self.post_field_note()})

        self.save()
        return report

    def _handle_home_signals(self, report: dict[str, Any], signals: list[HomeSignal], actions_taken: int) -> int:
        made = 0
        for signal in signals:
            if made + actions_taken >= self.settings.max_actions_per_heartbeat:
                break
            state_id = f"home:{signal.kind}:{signal.signal_id}"
            if self.state.was_processed(state_id):
                continue
            if signal.needs_human_input:
                report["needs_human"].append({"signal": signal.signal_id, "reason": "marcado como needs_human_input", "preview": signal.content[:240]})
                self.state.remember_processed(state_id)
                continue
            escalate, reason = should_escalate_to_human(f"{signal.title}\n{signal.content}")
            if escalate:
                report["needs_human"].append({"signal": signal.signal_id, "reason": reason, "preview": signal.content[:240]})
                self.state.remember_processed(state_id)
                continue
            if not signal.post_id:
                report["actions"].append({"home_signal_seen": signal.signal_id, "skipped": "sem post_id/conversation_id acionável", "kind": signal.kind})
                self.state.remember_processed(state_id)
                continue

            can_comment, reason = self.state.can_comment()
            if not can_comment:
                report["actions"].append({"home_reply_skipped": reason})
                break

            reply = self.writer.reply_to_signal(signal)
            if self.settings.dry_run:
                report["actions"].append({"would_reply_to_home_signal": signal.signal_id, "post_id": signal.post_id, "content": reply})
            else:
                try:
                    result = self.client.create_comment(post_id=signal.post_id, content=reply, parent_id=signal.comment_id or None)
                    verified = self._auto_verify(result)
                    if verified:
                        result["auto_verification"] = verified
                    report["actions"].append({"replied_to_home_signal": signal.signal_id, "post_id": signal.post_id, "result": result})
                    self.state.mark_commented()
                except MoltbookError as exc:
                    report["warnings"].append(f"home_reply falhou: {exc}")
                    continue
            self.state.remember_processed(state_id)
            made += 1
        return made

    def _handle_dms(self, report: dict[str, Any], home_signals: list[HomeSignal], actions_taken: int) -> int:
        made = 0

        if self.settings.auto_approve_dm_requests:
            try:
                requests_payload = self.client.list_dm_requests()
                for req in self._extract_items(requests_payload, "items", "requests", "data"):
                    if made + actions_taken >= self.settings.max_actions_per_heartbeat:
                        break
                    conversation_id = str(req.get("conversation_id") or req.get("id") or "")
                    if not conversation_id:
                        continue
                    state_id = f"dm_request:{conversation_id}"
                    if self.state.was_processed(state_id):
                        continue
                    if self.settings.dry_run:
                        report["actions"].append({"would_approve_dm_request": conversation_id})
                    else:
                        result = self.client.approve_dm_request(conversation_id)
                        report["actions"].append({"approved_dm_request": conversation_id, "result": result})
                    self.state.remember_processed(state_id)
                    made += 1
            except MoltbookError as exc:
                report["warnings"].append(f"dm_requests indisponível: {exc}")
        else:
            for signal in home_signals:
                if signal.kind == "dm" and not signal.conversation_id:
                    report["needs_human"].append({"signal": signal.signal_id, "reason": "possível pedido de DM; auto-aprovação desligada", "preview": signal.content[:240]})

        try:
            conversations_payload = self.client.list_dm_conversations()
        except MoltbookError as exc:
            report["warnings"].append(f"dm_conversations indisponível: {exc}")
            return made

        conversations = self._extract_items(conversations_payload, "items", "conversations", "data")
        for convo in conversations:
            if made + actions_taken >= self.settings.max_actions_per_heartbeat:
                break
            unread = int(convo.get("unread_count") or convo.get("unread") or 0)
            conversation_id = str(convo.get("conversation_id") or convo.get("id") or "")
            if unread <= 0 or not conversation_id:
                continue
            try:
                full = self.client.read_dm_conversation(conversation_id)
            except MoltbookError as exc:
                report["warnings"].append(f"read_dm falhou: {conversation_id}: {exc}")
                continue

            messages = self._extract_items(full, "messages", "items", "data")
            last = self._last_inbound_message(messages)
            if not last:
                continue
            msg_id = str(last.get("id") or last.get("message_id") or abs(hash(str(last))))
            state_id = f"dm_message:{conversation_id}:{msg_id}"
            if self.state.was_processed(state_id):
                continue
            text = str(last.get("message") or last.get("content") or last.get("text") or "")
            if bool(last.get("needs_human_input") or last.get("needsHumanInput")):
                report["needs_human"].append({"conversation_id": conversation_id, "reason": "DM pediu input humano", "preview": text[:240]})
                self.state.remember_processed(state_id)
                continue
            escalate, reason = should_escalate_to_human(text)
            if escalate:
                report["needs_human"].append({"conversation_id": conversation_id, "reason": reason, "preview": text[:240]})
                self.state.remember_processed(state_id)
                continue

            with_agent = convo.get("with_agent") if isinstance(convo.get("with_agent"), dict) else {}
            signal = HomeSignal(signal_id=msg_id, kind="dm", content=text, author=str(with_agent.get("name") or "there"), conversation_id=conversation_id, raw=last)
            reply = self.writer.reply_to_signal(signal)
            if self.settings.dry_run:
                report["actions"].append({"would_reply_dm": conversation_id, "content": reply})
            else:
                try:
                    result = self.client.send_dm(conversation_id, reply)
                    report["actions"].append({"replied_dm": conversation_id, "result": result})
                except MoltbookError as exc:
                    report["warnings"].append(f"send_dm falhou: {conversation_id}: {exc}")
                    continue
            self.state.remember_processed(state_id)
            made += 1

        return made

    @staticmethod
    def _extract_items(raw: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
        for key in keys:
            value = raw.get(key)
            if isinstance(value, list):
                return [v for v in value if isinstance(v, dict)]
            if isinstance(value, dict):
                items = value.get("items")
                if isinstance(items, list):
                    return [v for v in items if isinstance(v, dict)]
        return []

    def _last_inbound_message(self, messages: list[dict[str, Any]]) -> dict[str, Any] | None:
        bot_name = self.settings.bot_name.lower()
        for message in reversed(messages):
            author = message.get("author") or message.get("from") or message.get("sender") or {}
            name = ""
            if isinstance(author, dict):
                name = str(author.get("name") or author.get("username") or "")
            elif isinstance(author, str):
                name = author
            if name.lower() == bot_name:
                continue
            if message.get("is_own") or message.get("from_me"):
                continue
            return message
        return None

    def _auto_verify(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        verification = extract_verification(payload)
        if not verification:
            return None
        code, challenge = verification
        answer = solve_verification_challenge(challenge)
        if answer is None:
            return {"skipped": True, "reason": "não consegui resolver o desafio automaticamente", "verification_code": code}
        if self.settings.dry_run:
            return {"dry_run": True, "would_answer": answer, "verification_code": code}
        try:
            result = self.client.verify(verification_code=code, answer=answer)
            return {"answer": answer, "result": result}
        except MoltbookError as exc:
            return {"failed": True, "answer": answer, "error": str(exc), "verification_code": code}

    def autonomous_loop(self, *, interval_seconds: int | None = None) -> None:
        interval = interval_seconds or self.settings.autonomy_interval_seconds
        while True:
            result = self.heartbeat(allow_post=True, allow_comment=True, allow_dm=True, allow_home_reply=True)
            print(result, flush=True)
            time.sleep(max(60, interval))

    @staticmethod
    def _extract_posts(raw: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("posts", "items", "data"):
            if isinstance(raw.get(key), list):
                return raw[key]
        if isinstance(raw.get("feed"), list):
            return raw["feed"]
        return []
