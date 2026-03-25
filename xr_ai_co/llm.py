"""§14 LLM provider — Anthropic (Claude) with §17.1 transient retry + usage tracking."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from xr_ai_co.config import LLMConfig

log = logging.getLogger(__name__)

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]


@dataclass
class Usage:
    """Accumulated token usage across calls."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResponse:
    text: str
    usage: Usage = field(default_factory=Usage)
    raw: Any = None
    stop_reason: str | None = None


class LLMProviderError(Exception):
    """Wraps provider-specific errors with classification."""

    def __init__(self, message: str, *, transient: bool = False, status: int | None = None):
        super().__init__(message)
        self.transient = transient
        self.status = status


class LLMProvider:
    """Single-provider abstraction for Anthropic (Claude).

    §17.1: wall-clock timeout, bounded transient retries with backoff,
    fail-fast on auth/config errors.
    §17.2: tracks usage for budget_counters.
    """

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.cumulative_usage = Usage()
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if anthropic is None:
            raise LLMProviderError("anthropic package not installed (pip install anthropic)")
        api_key = self.config.api_key
        if not api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY not set", transient=False, status=401)
        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=self.config.llm_call_timeout_sec,
        )
        return self._client

    def chat(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """§17.1 bounded retry loop wrapping Anthropic messages.create."""
        client = self._ensure_client()
        last_err: Exception | None = None
        max_retries = self.config.max_retries_transient_api

        for attempt in range(1 + max_retries):
            try:
                resp = client.messages.create(
                    model=self.config.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                    temperature=temperature,
                )
                usage = Usage(
                    prompt_tokens=resp.usage.input_tokens,
                    completion_tokens=resp.usage.output_tokens,
                )
                self.cumulative_usage.prompt_tokens += usage.prompt_tokens
                self.cumulative_usage.completion_tokens += usage.completion_tokens

                text_parts = [block.text for block in resp.content if hasattr(block, "text")]
                return LLMResponse(
                    text="\n".join(text_parts),
                    usage=usage,
                    raw=resp,
                    stop_reason=resp.stop_reason,
                )
            except Exception as e:
                last_err = e
                transient = _is_transient(e)
                if not transient or attempt >= max_retries:
                    raise LLMProviderError(
                        str(e),
                        transient=transient,
                        status=_status_code(e),
                    ) from e
                wait = min(2 ** attempt, 30)
                log.warning("transient LLM error (attempt %d/%d), retry in %ds: %s",
                            attempt + 1, max_retries, wait, e)
                time.sleep(wait)

        raise LLMProviderError(str(last_err), transient=True) from last_err


def _is_transient(exc: Exception) -> bool:
    status = _status_code(exc)
    if status in (429, 502, 503, 529):
        return True
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    cls_name = type(exc).__name__
    if "timeout" in cls_name.lower() or "overloaded" in cls_name.lower():
        return True
    return False


def _status_code(exc: Exception) -> int | None:
    code = getattr(exc, "status_code", None)
    if code is not None:
        return int(code)
    resp = getattr(exc, "response", None)
    if resp is not None:
        sc = getattr(resp, "status_code", None)
        if sc is not None:
            return int(sc)
    return None
