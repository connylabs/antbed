from openai import OpenAI
from pydantic import BaseModel, Field

from ..clients import openai_client
from .agent import Agent, ContextTooLargeError

PROMPT = """
Generate a comprehensive and detailed shorter version of the given text in the same language as the original text.
Additionally, include a short description, a title for the table of contents, and tags for indexing.
The shorter version is not a summary but a version that has reduced redundancy in information and rewriting
sentences using fewer words or characters without changing the essence.
The short version can't be less than 25% the original size and will be exclusively machine processed by LLM,
so it's okay if the sentences are not grammatically correct to reduce size.

# Steps
1. **Read and Comprehend**: Carefully read the entire text to fully understand its content and context.
2. **Identify Key Information**: Note down all critical points, important data, and any context that is essential for
   understanding.
3. **Preserve Context**: Ensure all critical context is preserved, even if it means including more information rather
   than less.
4. **Timeline and Chronology**: The document structure must not be altered. Summarize each paragraph and clearly
   highlight chronology.
5. **Rewrite for Brevity**: Rewrite sentences to reduce token count while keeping the original meaning, allowing
   grammatical flexibility.
6. **Revise and Verify**: Review the shortened version to ensure no important information is omitted and refine for
   clarity and coherence. All dates, all numbers, all names, all entities must be present in the shorter version.
7. **Language Handling**: Ensure the shorter version is in the same language as the input.
8. **Additional Content**: Add a short description (2-3 sentences) of the text, a suitable document title for a table
   of contents, and a list of tags for indexing.

# Output Format

Produce a json output
fields are:
    short_version: str = Field(..., description="The shorter version but accurate and exaustive of the original text.")
    description: str = Field(..., description="A short description of the content, 2-3 sentences")
    title: str = Field(..., description="Title for the table of contents.")
    language: str = Field(...,
                          description="The language of the original text. E.g., 'en' for English. 'de' for German.",
                          examples=["en", 'de', 'fr'])

    tags: list[str] = Field(default_factory=list, description="List of tags for indexing")

    

# Notes

- When uncertain about the importance of information, include it to preserve the context fully.
- The most import is to not lose any information. Reducing size is secondary"
"""


class SummaryInput(BaseModel):
    content: str = Field(...)


class Entity(BaseModel):
    name: str = Field(..., description="Name of the entity")
    type: str = Field(..., description="Type of the entity. E.g., 'name', 'date', 'number', 'place', etc.")


class LocalSummaryOutput(BaseModel):
    short_version: str = Field(..., description="The shorter version but accurate and exaustive of the original text.")
    description: str = Field(..., description="A short description of the content, 2-3 sentences")
    title: str = Field(..., description="Title for the table of contents.")
    tags: list[str] = Field(default_factory=list, description="List of tags for indexing")
    language: str = Field(
        ..., description="The language of the original text. E.g., 'en' for English. 'de' for German."
    )


class SummaryAgent(Agent[SummaryInput, LocalSummaryOutput]):  # type: ignore[type-var]
    max_tokens = 150000  # enable 50k tokens output
    # model = "o3-mini"
    model = "gemini-2.0-flash"

    def __init__(self, client: OpenAI | None = None, client_name: str | None = None, truncate: bool = True):
        self._truncate = truncate
        if not client and client_name:
            client = openai_client(client_name)
        super().__init__(client)

    def _get_content(self, values: SummaryInput) -> str:
        content = values.model_dump_json()
        if self._truncate:
            content = self.truncate(content, self.max_tokens)
        else:
            token_count = self.count_tokens(content)
            if token_count > self.max_tokens:
                raise ContextTooLargeError(
                    f"Content too long. Token count: {token_count}, Max tokens: {self.max_tokens}"
                )
        return content

    def run(self, values: SummaryInput) -> LocalSummaryOutput | None:
        content = self._get_content(values)
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "developer", "content": PROMPT},
                {"role": "user", "content": content},
            ],
            max_tokens=self.max_tokens,
            response_format=LocalSummaryOutput,
            # reasoning_effort="high",
        )
        res = response.choices[0].message.parsed
        return res
