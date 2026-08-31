import httpx

from app.config.settings import Settings
from app.providers.base import LLMProvider
from app.providers.errors import ProviderConfigurationError
from app.providers.mock import MockProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


def create_provider(settings: Settings, client: httpx.AsyncClient) -> LLMProvider:
    provider = settings.nexus_llm_provider.lower()
    if provider == "mock":
        return MockProvider()
    if provider == "ollama":
        return OllamaProvider(
            client,
            settings.nexus_ollama_base_url,
            settings.nexus_ollama_model,
        )
    if provider == "openai_compatible":
        return OpenAICompatibleProvider(
            client,
            settings.nexus_llm_base_url,
            settings.nexus_llm_model,
            settings.nexus_llm_api_key,
        )
    raise ProviderConfigurationError(
        f"Unsupported NEXUS_LLM_PROVIDER: {settings.nexus_llm_provider}"
    )
