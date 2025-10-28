from abc import abstractmethod
from typing import TypeVar

import tiktoken
from openai import OpenAI
from pydantic import BaseModel

from ..clients import openai_client

InputModel = TypeVar("InputModel", bound=BaseModel)
OutputModel = TypeVar("OutputModel", bound=BaseModel)


class ContextTooLargeError(ValueError): ...


class Agent[InputModel, OutputModel]:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.client = client if client else openai_client()

    @abstractmethod
    def run(self, values: InputModel) -> OutputModel | None: ...

    def count_tokens(self, content, model="gpt-4o") -> int:
        encoder = tiktoken.encoding_for_model(model)
        return len(encoder.encode(content))

    def truncate(self, content, max_tokens, model="gpt-4o") -> str:
        encoder = tiktoken.encoding_for_model(model)
        return encoder.decode(encoder.encode(content)[0 : max_tokens - 1])
