"""Narrator client implementations."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any

from .models import NarratorClient, NarratorResponse


class FakeNarratorClient:
    """
    Fake narrator client for testing.
    
    Returns predefined responses in order.
    Fully deterministic, no network access.
    """
    
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.call_count = 0
    
    def generate(self, prompt: str) -> str:
        """Return next predefined response."""
        if self.call_count >= len(self.responses):
            raise ValueError(f"FakeNarratorClient: no more responses (called {self.call_count + 1} times, only {len(self.responses)} responses provided)")
        
        response = self.responses[self.call_count]
        self.call_count += 1
        return response


class OpenAICompatibleClient:
    """
    Real narrator client using OpenAI-compatible API.
    
    Configuration via environment variables:
    - TGN_NARRATOR_BASE_URL: API base URL
    - TGN_NARRATOR_API_KEY: API key (never logged)
    - TGN_NARRATOR_MODEL: Model name
    
    Uses stdlib urllib.request to avoid adding dependencies.
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 30,
    ):
        if not base_url:
            raise ValueError("base_url is required (set TGN_NARRATOR_BASE_URL)")
        if not api_key:
            raise ValueError("api_key is required (set TGN_NARRATOR_API_KEY)")
        if not model:
            raise ValueError("model is required (set TGN_NARRATOR_MODEL)")
        
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
    
    def generate(self, prompt: str) -> str:
        """Generate narration via OpenAI-compatible API."""
        url = f"{self.base_url}/v1/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500,
        }
        
        data = json.dumps(payload).encode("utf-8")
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                text = response_data["choices"][0]["message"]["content"]
                return text.strip()
        
        except urllib.error.URLError as e:
            raise RuntimeError(f"Narrator API request failed: {e}") from e
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Narrator API response malformed: {e}") from e


def create_client_from_env() -> OpenAICompatibleClient:
    """
    Create OpenAI-compatible client from environment variables.
    
    Required env vars:
    - TGN_NARRATOR_BASE_URL
    - TGN_NARRATOR_API_KEY
    - TGN_NARRATOR_MODEL
    
    Raises ValueError if any are missing.
    """
    import os
    
    base_url = os.environ.get("TGN_NARRATOR_BASE_URL", "")
    api_key = os.environ.get("TGN_NARRATOR_API_KEY", "")
    model = os.environ.get("TGN_NARRATOR_MODEL", "")
    
    return OpenAICompatibleClient(base_url, api_key, model)
