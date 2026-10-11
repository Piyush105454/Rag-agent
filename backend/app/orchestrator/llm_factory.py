"""
llm_factory.py -- Unified LLM client factory supporting multiple providers.

LLM_PROVIDER env var selects the backend:
  groq      -> AsyncGroq (default, model: llama-3.1-70b-versatile)
  openai    -> AsyncOpenAI
  anthropic -> AsyncAnthropic
  gemini    -> google-generativeai async
  vllm      -> AsyncOpenAI with custom base_url (self-hosted)

All providers are wrapped behind a common LLMClient interface exposing:
  complete(messages, system) -> str          (non-streaming)
  stream(messages, system)   -> AsyncGenerator[str, None]  (token-by-token)

Callers never import provider SDKs directly -- they call get_llm_client().
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncGenerator, List, Optional
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv("../.env")

from app.config import settings

# ── Settings helpers ──────────────────────────────────────────────────────

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


PROVIDER = _env("LLM_PROVIDER", settings.llm_provider).lower()
GROQ_MODEL = _env("GROQ_MODEL", settings.groq_model)
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-1.5-pro")
VLLM_BASE_URL = _env("VLLM_BASE_URL", "http://localhost:8000/v1")
VLLM_MODEL = _env("VLLM_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct")

MAX_TOKENS = int(_env("LLM_MAX_TOKENS", "2048"))
TEMPERATURE = float(_env("LLM_TEMPERATURE", "0.1"))


# ── Base wrapper ──────────────────────────────────────────────────────────

class LLMClient:
    """Abstract base; concrete subclasses implement complete and stream."""

    async def complete(self, messages: List[dict], system: str = "") -> str:
        raise NotImplementedError

    async def stream(
        self, messages: List[dict], system: str = ""
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError
        yield  # make it a generator


# ── Groq ──────────────────────────────────────────────────────────────────

class GroqClient(LLMClient):
    """Wrapper around the official groq Python SDK AsyncGroq client."""

    def __init__(self) -> None:
        from groq import AsyncGroq  # type: ignore[import]
        self._client = AsyncGroq(api_key=_env("GROQ_API_KEY"))
        self._model = GROQ_MODEL

    def _build_msgs(self, messages: List[dict], system: str) -> List[dict]:
        out: List[dict] = []
        if system:
            out.append({"role": "system", "content": system})
        out.extend(messages)
        return out

    async def complete(self, messages: List[dict], system: str = "") -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=self._build_msgs(messages, system),
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            stream=False,
        )
        return resp.choices[0].message.content or ""

    async def stream(
        self, messages: List[dict], system: str = ""
    ) -> AsyncGenerator[str, None]:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=self._build_msgs(messages, system),
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# ── OpenAI ────────────────────────────────────────────────────────────────

class OpenAIClient(LLMClient):
    """Wrapper around openai AsyncOpenAI."""

    def __init__(self) -> None:
        from openai import AsyncOpenAI  # type: ignore[import]
        self._client = AsyncOpenAI(api_key=_env("OPENAI_API_KEY"))
        self._model = OPENAI_MODEL

    def _build_msgs(self, messages: List[dict], system: str) -> List[dict]:
        out: List[dict] = []
        if system:
            out.append({"role": "system", "content": system})
        out.extend(messages)
        return out

    async def complete(self, messages: List[dict], system: str = "") -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=self._build_msgs(messages, system),
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        return resp.choices[0].message.content or ""

    async def stream(
        self, messages: List[dict], system: str = ""
    ) -> AsyncGenerator[str, None]:
        async for chunk in await self._client.chat.completions.create(
            model=self._model,
            messages=self._build_msgs(messages, system),
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            stream=True,
        ):
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# ── Anthropic ─────────────────────────────────────────────────────────────

class AnthropicClient(LLMClient):
    """Wrapper around anthropic AsyncAnthropic."""

    def __init__(self) -> None:
        from anthropic import AsyncAnthropic  # type: ignore[import]
        self._client = AsyncAnthropic(api_key=_env("ANTHROPIC_API_KEY"))
        self._model = ANTHROPIC_MODEL

    async def complete(self, messages: List[dict], system: str = "") -> str:
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system or None,
            messages=messages,
        )
        return resp.content[0].text if resp.content else ""

    async def stream(
        self, messages: List[dict], system: str = ""
    ) -> AsyncGenerator[str, None]:
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system or None,
            messages=messages,
        ) as s:
            async for text in s.text_stream:
                yield text


# ── Gemini ────────────────────────────────────────────────────────────────

class GeminiClient(LLMClient):
    """Wrapper around google-generativeai async interface."""

    def __init__(self) -> None:
        import google.generativeai as genai  # type: ignore[import]
        genai.configure(api_key=_env("GEMINI_API_KEY"))
        self._model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=None,  # injected per-call
        )

    def _full_prompt(self, messages: List[dict], system: str) -> str:
        parts = []
        if system:
            parts.append(f"[System]: {system}")
        for m in messages:
            role = m.get("role", "user").capitalize()
            parts.append(f"[{role}]: {m.get('content', '')}")
        return "\\n\\n".join(parts)

    async def complete(self, messages: List[dict], system: str = "") -> str:
        resp = await self._model.generate_content_async(
            self._full_prompt(messages, system)
        )
        return resp.text or ""

    async def stream(
        self, messages: List[dict], system: str = ""
    ) -> AsyncGenerator[str, None]:
        async for chunk in await self._model.generate_content_async(
            self._full_prompt(messages, system), stream=True
        ):
            if chunk.text:
                yield chunk.text


# ── vLLM (OpenAI-compatible) ──────────────────────────────────────────────

class VLLMClient(LLMClient):
    """AsyncOpenAI pointed at a self-hosted vLLM endpoint."""

    def __init__(self) -> None:
        from openai import AsyncOpenAI  # type: ignore[import]
        self._client = AsyncOpenAI(
            api_key=_env("VLLM_API_KEY", "EMPTY"),
            base_url=VLLM_BASE_URL,
        )
        self._model = VLLM_MODEL

    def _build_msgs(self, messages: List[dict], system: str) -> List[dict]:
        out: List[dict] = []
        if system:
            out.append({"role": "system", "content": system})
        out.extend(messages)
        return out

    async def complete(self, messages: List[dict], system: str = "") -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=self._build_msgs(messages, system),
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        return resp.choices[0].message.content or ""

    async def stream(
        self, messages: List[dict], system: str = ""
    ) -> AsyncGenerator[str, None]:
        async for chunk in await self._client.chat.completions.create(
            model=self._model,
            messages=self._build_msgs(messages, system),
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            stream=True,
        ):
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# ── Factory ───────────────────────────────────────────────────────────────

_REGISTRY: dict[str, type[LLMClient]] = {
    "groq": GroqClient,
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "gemini": GeminiClient,
    "vllm": VLLMClient,
}

_instance: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """
    Return a (cached) LLMClient for the configured provider.

    Reads LLM_PROVIDER env var once at first call; subsequent calls return
    the same instance (singleton per process lifetime).
    """
    global _instance
    if _instance is None:
        cls = _REGISTRY.get(PROVIDER)
        if cls is None:
            raise ValueError(
                f"Unknown LLM_PROVIDER={PROVIDER!r}. "
                f"Valid options: {list(_REGISTRY)}"
            )
        _instance = cls()
    return _instance