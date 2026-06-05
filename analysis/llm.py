from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.config import Settings


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required.")
        self.settings = settings

    def chat_text(self, messages: list[ChatMessage], temperature: float = 0.2) -> str:
        payload = build_chat_payload(self.settings.llm_model, messages, temperature)
        response = post_chat_completion(
            base_url=self.settings.llm_base_url,
            api_key=self.settings.llm_api_key,
            payload=payload,
            timeout=self.settings.llm_timeout,
        )
        return parse_chat_text(response)


def build_chat_payload(model: str, messages: list[ChatMessage], temperature: float = 0.2) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": message.role, "content": message.content} for message in messages],
        "temperature": temperature,
    }


def post_chat_completion(base_url: str, api_key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/chat/completions"
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise LLMError(f"LLM request failed: {exc.code} {message}") from exc


def parse_chat_text(response: dict[str, Any]) -> str:
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("LLM response did not contain choices[0].message.content.") from exc
