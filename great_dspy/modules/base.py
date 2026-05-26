"""
GREAT Pre-Estimation — Lightweight LM Module Base.

Provides a DSPy-compatible module pattern that works with any
OpenAI-compatible API provider. When dspy-ai is available, switch
to real DSPy by changing the base class.
"""
from __future__ import annotations

import json
import os
import logging
from typing import Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class LMClient:
    """
    Lightweight OpenAI-compatible LM client.

    Can be swapped for DSPy's LM class when available:
        import dspy
        lm = dspy.LM(model="openai/deepseek-chat")
    """

    def __init__(self, model: str = "deepseek/deepseek-chat",
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = base_url or "https://api.openai.com/v1"

        # Provider routing
        if "deepseek" in model.lower():
            self.base_url = "https://api.deepseek.com/v1"
        elif "openai" in model.lower():
            self.base_url = base_url or "https://api.openai.com/v1"

    def complete(self, system: str, prompt: str, max_tokens: int = 500,
                 temperature: float = 0.1) -> str:
        """Make an LM completion via OpenAI-compatible API."""
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "model": self.model.split("/")[-1] if "/" in self.model else self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
            return resp["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"LM call failed: {e}")
            return ""


class Module:
    """
    Base class for pipeline modules.

    In DSPy, this becomes:
        class MyModule(dspy.Module):
            def __init__(self):
                super().__init__()
                self.predict = dspy.ChainOfThought(MySignature)
    """

    def __init__(self, lm: Optional[LMClient] = None):
        self.lm = lm or LMClient()

    def call_lm(self, system: str, prompt: str, **kwargs) -> str:
        """Call the LM with system prompt and user prompt."""
        return self.lm.complete(system, prompt, **kwargs)

    def parse_bool(self, value: str) -> bool:
        """Parse a string response to boolean."""
        if not value:
            return False
        return value.strip().lower().startswith("true")


# Re-export key types for convenience
from dataclasses import dataclass, field
from typing import Any, Optional