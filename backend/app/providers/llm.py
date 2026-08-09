"""LLM provider interface + tiered implementations (cost-performance-analysis.md §1).

Two tiers, never one model:
- cheap  (routing, classification, escalation, summarization)
- premium (decision brief synthesis, contradiction validation, risk assessment)

OpenAIChat and AnthropicChat both implement `complete()`; swap by config
(cheap_provider / premium_provider). Providers import lazily so the app boots
without API keys.
"""

from abc import ABC, abstractmethod

from app.core.config import Settings, get_settings


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 800,
        json_mode: bool = True,
    ) -> str:
        """Run one completion and return the text (JSON string when json_mode)."""


class OpenAIChat(LLMProvider):
    name = "openai"

    def __init__(self, model: str, api_key: str | None) -> None:
        from openai import OpenAI

        self.model = model
        self._client = OpenAI(api_key=api_key)

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 800,
        json_mode: bool = True,
    ) -> str:
        from openai import OpenAIError

        kwargs = {"model": self.model, "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **kwargs,
            )
        except OpenAIError as exc:  # pragma: no cover
            raise RuntimeError(f"openai failure: {exc}") from exc
        return resp.choices[0].message.content or ""


class AnthropicChat(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None) -> None:
        from anthropic import Anthropic

        self.model = model
        self._client = Anthropic(api_key=api_key)

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 800,
        json_mode: bool = True,
    ) -> str:
        from anthropic import AnthropicError

        try:
            resp = self._client.messages.create(
                model=self.model,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": user}],
            )
        except AnthropicError as exc:  # pragma: no cover
            raise RuntimeError(f"anthropic failure: {exc}") from exc
        return "".join(block.text for block in resp.content if block.type == "text")


def build_llm(provider_name: str, model: str, settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if provider_name == "openai":
        return OpenAIChat(model, settings.openai_api_key)
    if provider_name == "anthropic":
        return AnthropicChat(model, settings.anthropic_api_key)
    raise ValueError(f"unknown provider: {provider_name}")


def get_llm(tier: str, settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if tier == "cheap":
        provider_name, model = settings.cheap_provider, settings.cheap_model
    elif tier == "premium":
        provider_name, model = settings.premium_provider, settings.premium_model
    elif tier == "brief":
        provider_name = settings.think9_brief_provider
        model = settings.think9_brief_model or settings.premium_model
    else:
        raise ValueError(f"unknown tier: {tier}")
    return build_llm(provider_name, model, settings)
