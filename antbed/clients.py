from functools import cache

import logfire
import qdrant_client as qc
from openai import OpenAI

from antbed.config import config


@cache
def qdrant_client() -> qc.QdrantClient:
    """Create a QdrantClient instance"""
    conf = config().qdrant
    return qc.QdrantClient(
        host=conf.host,
        port=conf.port,
        grpc_port=conf.grpc_port,
        api_key=conf.api_key,
        https=conf.https,
        prefer_grpc=conf.prefer_grpc,
    )


@cache
def openai_client(project_name: str = "") -> OpenAI:
    """Create a OpenAI instance with the given api_key
    It cache the answer for the same api_key
    use openai.cache_clear() to clear the cache
    """
    if not project_name:
        project = config().openai.projects[0]
    else:
        project = config().openai.get_project(project_name)
        if not project:
            raise ValueError(f"Project {project_name} not found")
    openaiconf = config().openai
    api_key = project.api_key
    organization = openaiconf.organization_id
    base_url = project.url
    client = OpenAI(
        api_key=api_key,
        organization=organization,
        project=project.project_id,
        base_url=base_url,
    )
    logfire.instrument_openai(client)
    return client
