"""Optional Claude text provider for coding, documents, and background reasoning."""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests


@dataclass
class TextResponse:
    text: str


class ClaudeProvider:
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("CLAUDE_API_KEY", "")
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-3-5-haiku-latest")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def generate_content(self, contents: str | list, max_tokens: int = 4096) -> TextResponse:
        if not self.available:
            raise RuntimeError("CLAUDE_API_KEY is not configured")
        prompt = contents if isinstance(contents, str) else "\n\n".join(str(item) for item in contents)
        response = requests.post(
            self.API_URL,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": max(256, min(max_tokens, 200000)),
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        return TextResponse(text=text)


def get_text_provider(gemini_factory, model: str | None = None):
    """Select Claude when configured, otherwise retain the existing Gemini path."""
    provider = os.getenv("FRIDAY_TEXT_PROVIDER", "auto").lower().strip()
    claude = ClaudeProvider(model=model)
    if provider == "claude" or (provider == "auto" and claude.available):
        return claude
    return gemini_factory()
