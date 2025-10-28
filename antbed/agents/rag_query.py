from pydantic import Field

from ..models import BaseModel, ConfigDict
from .agent import Agent

RAG_QUERY_SYSTEM = """
Translate user input queries into the requested language, if present, to improve the retrieval of relevant documents
using a RAG system. This process should account for potentially insufficient user queries by allowing for multiple
search queries to enhance document retrieval.

# Steps

1. Transform each user query into one or multiple search queries that are adequately detailed for effective document
   retrieval. The query should be long enough that relevant information is retrieved after the
   vectorization/embedding process.
2. Translate these search queries into requested language if present.
3. Return the translated queries in the specified JSON format.

# Output Format

- JSON object with key "queries" and the translated queries as values.
- Example format: {"language": "de", "queries": ["translated query1", "translated query2"]}

# Notes

- Ensure accuracy in translation to maintain the integrityand intent of the original queries.
"""


class RagQuery(BaseModel):
    model_config = ConfigDict(extra="allow")
    queries: list[str] = Field(..., description="A list of translated queries.")
    language: str | None = Field(None, description="The language code for the translation, e.g., 'de' for German.")


class RagQueryAgent(Agent[RagQuery, RagQuery]):  # type: ignore[type-var]
    def run(self, values: RagQuery) -> RagQuery | None:
        response = self.client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": RAG_QUERY_SYSTEM,
                },
                {"role": "user", "content": values.model_dump_json()},
            ],
            response_format=RagQuery,
            temperature=0.80,
            max_completion_tokens=100,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )
        res = response.choices[0].message.parsed
        return res
