from functools import cache

import logfire
from openai import OpenAI

from antbed.config import config


@cache
def embedding_client(project_name: str = "") -> OpenAI:
    """Create a OpenAI instance for embeddings with the given api_key
    It cache the answer for the same api_key
    use openai.cache_clear() to clear the cache
    """
    if not project_name:
        project = config().embeddings.projects[0]
    else:
        project = config().embeddings.get_project(project_name)
        if not project:
            raise ValueError(f"Project {project_name} not found in embeddings config")
    embedconf = config().embeddings
    api_key = project.api_key
    organization = embedconf.organization_id
    base_url = project.url
    client = OpenAI(
        api_key=api_key,
        organization=organization,
        project=project.project_id,
        base_url=base_url,
    )
    logfire.instrument_openai(client)
    return client
