from functools import cache

import logfire
from openai import OpenAI

from antbed.config import Config, EmbeddingProviderConfig, config as confload


class EmbeddingClient:
    def __init__(self, client: OpenAI):
        self._client = client

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        response = self._client.embeddings.create(input=texts, model=model)
        return [d.embedding for d in response.data]


@cache
def embedding_client(provider: str | None = None, use_litellm: bool = False) -> EmbeddingClient:
    """Create an embedding client instance."""
    config: Config = confload()
    # This ignores use_litellm for now
    provider_conf: EmbeddingProviderConfig = config.embeddings.get_provider(provider)

    api_key = provider_conf.api_key
    if not api_key and provider_conf.api_key_ref:
        if provider_conf.api_key_ref == "llms.openai":
            # This part is tricky. 'llms.openai' in `antgent` is probably a key in `llms.providers`.
            # But the existing `openai_client` uses `config().openai`.
            # And the default value for `api_key_ref` is `llms.openai`.
            # I will assume it refers to `config().openai` for now.
            api_key = config.openai.projects[0].api_key

    # For now, only handle openai provider.
    if provider_conf.name != "openai":
        raise NotImplementedError(f"Embedding provider '{provider_conf.name}' not supported yet.")

    client = OpenAI(
        api_key=api_key,
        organization=provider_conf.organization_id,
        project=provider_conf.project_id,
        base_url=provider_conf.base_url,
    )
    logfire.instrument_openai(client)

    return EmbeddingClient(client)
