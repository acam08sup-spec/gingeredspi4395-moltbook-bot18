from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests

from .config import SAFE_API_BASE
from .safety import safe_outbound_text


class MoltbookError(RuntimeError):
    pass


@dataclass
class MoltbookClient:
    api_key: str | None = None
    api_base: str = SAFE_API_BASE
    timeout: int = 30

    def __post_init__(self) -> None:
        self.api_base = self.api_base.rstrip("/")
        if self.api_base != SAFE_API_BASE:
            raise ValueError(f"api_base insegura. Use exatamente {SAFE_API_BASE}")

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.api_base}{path}"
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=self.headers,
                json=json_body,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise MoltbookError(f"Falha de conexão com Moltbook: {exc}") from exc

        if response.status_code >= 400:
            body = response.text[:1000]
            raise MoltbookError(f"Moltbook retornou HTTP {response.status_code}: {body}")

        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise MoltbookError(f"Resposta não-JSON do Moltbook: {response.text[:500]}") from exc

    def register_agent(self, name: str, description: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/agents/register",
            json_body={"name": safe_outbound_text(name, 80), "description": safe_outbound_text(description, 600)},
        )

    def status(self) -> dict[str, Any]:
        self._require_key()
        return self._request("GET", "/agents/status")

    def list_posts(self, *, sort: str = "new", limit: int = 10) -> dict[str, Any]:
        self._require_key()
        query = urlencode({"sort": sort, "limit": max(1, min(limit, 50))})
        return self._request("GET", f"/posts?{query}")

    def feed(self, *, sort: str = "new", limit: int = 10) -> dict[str, Any]:
        self._require_key()
        query = urlencode({"sort": sort, "limit": max(1, min(limit, 50))})
        return self._request("GET", f"/feed?{query}")

    def home(self) -> dict[str, Any]:
        self._require_key()
        return self._request("GET", "/home")

    def get_post(self, post_id: str) -> dict[str, Any]:
        self._require_key()
        return self._request("GET", f"/posts/{post_id}")

    def create_post(self, *, submolt: str, title: str, content: str) -> dict[str, Any]:
        self._require_key()
        return self._request(
            "POST",
            "/posts",
            json_body={
                "submolt": safe_outbound_text(submolt, 80),
                "title": safe_outbound_text(title, 200),
                "content": safe_outbound_text(content, 4000),
            },
        )

    def create_comment(self, *, post_id: str, content: str, parent_id: str | None = None) -> dict[str, Any]:
        self._require_key()
        body: dict[str, Any] = {"content": safe_outbound_text(content, 2500)}
        if parent_id:
            body["parent_id"] = parent_id

        try:
            return self._request("POST", f"/posts/{post_id}/comments", json_body=body)
        except MoltbookError:
            body["post_id"] = safe_outbound_text(post_id, 120)
            return self._request("POST", "/comments", json_body=body)

    def check_dms(self) -> dict[str, Any]:
        self._require_key()
        return self._request("GET", "/agents/dm/check")

    def list_dm_requests(self) -> dict[str, Any]:
        self._require_key()
        return self._request("GET", "/agents/dm/requests")

    def approve_dm_request(self, conversation_id: str) -> dict[str, Any]:
        self._require_key()
        return self._request("POST", f"/agents/dm/requests/{safe_outbound_text(conversation_id, 120)}/approve")

    def reject_dm_request(self, conversation_id: str, *, block: bool = False) -> dict[str, Any]:
        self._require_key()
        body = {"block": bool(block)} if block else None
        return self._request("POST", f"/agents/dm/requests/{safe_outbound_text(conversation_id, 120)}/reject", json_body=body)

    def list_dm_conversations(self) -> dict[str, Any]:
        self._require_key()
        return self._request("GET", "/agents/dm/conversations")

    def read_dm_conversation(self, conversation_id: str) -> dict[str, Any]:
        self._require_key()
        return self._request("GET", f"/agents/dm/conversations/{safe_outbound_text(conversation_id, 120)}")

    def send_dm(self, conversation_id: str, message: str, *, needs_human_input: bool = False) -> dict[str, Any]:
        self._require_key()
        body: dict[str, Any] = {"message": safe_outbound_text(message, 1800)}
        if needs_human_input:
            body["needs_human_input"] = True
        return self._request("POST", f"/agents/dm/conversations/{safe_outbound_text(conversation_id, 120)}/send", json_body=body)

    def list_submolts(self) -> dict[str, Any]:
        self._require_key()
        return self._request("GET", "/submolts")


    def verify(self, *, verification_code: str, answer: str) -> dict[str, Any]:
        self._require_key()
        return self._request(
            "POST",
            "/verify",
            json_body={
                "verification_code": safe_outbound_text(verification_code, 200),
                "answer": safe_outbound_text(answer, 80),
            },
        )

    def _require_key(self) -> None:
        if not self.api_key:
            raise MoltbookError("MOLTBOOK_API_KEY não configurada.")
