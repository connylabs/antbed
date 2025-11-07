import datetime
import hashlib
import hmac
import json
import uuid
from collections.abc import Sequence
from enum import StrEnum
from typing import Any, ClassVar, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from antbed.db.models import (
    CollectionSchema,
    EmbeddingSchema,
    VectorSchema,
    VectorVFileSchema,
    VFileCollectionSchema,
    VFileSchema,
    VFileSplitSchema,
    VFileUploadSchema,
)


class OutputFormatEnum(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"


class SummaryOutputProtocol(Protocol):
    short_version: str
    tags: list[str] | None
    description: str
    title: str
    language: str


class SplitterType(StrEnum):
    RECURSIVE = "recursive"
    CHAR = "char"
    SEMANTIC = "semantic"
    SPACY = "spacy"


class EmbeddingModel(StrEnum):
    # OpenAI models
    OPENAI_LARGE = "text-embedding-3-large"
    OPENAI_SMALL = "text-embedding-3-small"
    # Cohere models
    COHERE_EMBED_V3 = "embed-english-v3.0"
    COHERE_EMBED_MULTILINGUAL_V3 = "embed-multilingual-v3.0"
    # Voyage AI models
    VOYAGE_LARGE_2 = "voyage-large-2"
    VOYAGE_CODE_2 = "voyage-code-2"


class ManagerEnum(StrEnum):
    OPENAI = "openai"
    QDRANT = "qdrant"
    NONE = "none"


class SplitterConfig(BaseModel):
    chunk_size: int = Field(default=800, title="Chunk Size", description="The size of the chunk to split the text into")
    chunk_overlap_perc: int = Field(
        default=50, title="Chunk Overlap Percentage", description="The percentage of overlap between chunks"
    )
    token_splitter: bool = Field(default=False, title="Token Splitter", description="Whether to use a token splitter")
    splitter_type: SplitterType = Field(
        default=SplitterType.RECURSIVE, title="Splitter Type", description="The type of splitter to use"
    )
    embedding_provider: str | None = Field(
        default=None, title="Embedding Provider", description="Embedding provider name (uses default if None)"
    )
    model: str = Field(
        default="text-embedding-3-large", title="Embedding Model", description="The model to use for embeddings"
    )

    def overlap(self):
        return self.chunk_size * self.chunk_overlap_perc // 100

    def config_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True).encode()).hexdigest()

    def name(self) -> str:
        model_name = self.model.replace("-", "_").replace(".", "_")
        return (
            f"{self.splitter_type.value}_{model_name}_c{self.chunk_size}_o{self.overlap()}_t{self.token_splitter}"
        ).lower()


class SplitDocument(BaseModel):
    start: int = Field(..., title="Start Index", description="The start index of the document")
    stop: int = Field(..., title="Stop Index", description="The stop index of the document")
    content: str = Field(..., title="Content", description="The content of the document")


class UploadRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")
    config: SplitterConfig = Field(default_factory=SplitterConfig, description="configuration of the document splitter")
    doc: VFileSchema = Field(...)
    manager: ManagerEnum = Field(default=ManagerEnum.NONE)
    skip_embedding: bool = Field(default=False)
    collection_name: str | None = Field(default=None)
    collection_id: uuid.UUID | None = Field(default=None)
    vector: VectorSchema | None = Field(default=None)
    vector_id: uuid.UUID | None = Field(default=None)
    summarize: bool = Field(default=True)
    resummarize: bool = Field(default=False)
    translate: str | None = Field(default=None)
    translate_summary: bool = Field(default=False)


class UploadRequestResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")
    config: SplitterConfig = Field(default_factory=SplitterConfig)
    manager: ManagerEnum = Field(default=ManagerEnum.NONE)
    skip_embedding: bool = Field(default=False)
    vfile: VFileSchema | None = Field(default=None)
    vfile_split: VFileSplitSchema | None = Field(default=None)
    colletion: CollectionSchema | None = Field(default=None)
    vector: VectorSchema | None = Field(default=None)
    embedding: EmbeddingSchema | None = Field(default=None)
    vector_vfile: VectorVFileSchema | None = Field(default=None)
    vfile_upload: VFileUploadSchema | None = Field(default=None)
    vfile_collection: VFileCollectionSchema | None = Field(default=None)


class UploadRequestIDs(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")
    config: SplitterConfig = Field(default_factory=SplitterConfig)
    manager: ManagerEnum = Field(default=ManagerEnum.NONE)
    skip_embedding: bool = Field(default=False)
    collection_name: str | None = Field(default=None)
    collection_id: uuid.UUID | None = Field(default=None)
    vfile_id: uuid.UUID | None = Field(default=None)
    vfile_split_id: uuid.UUID | None = Field(default=None)
    vector_id: uuid.UUID | None = Field(default=None)
    vector: VectorSchema | None = Field(default=None)
    vector_vfile_id: uuid.UUID | None = Field(default=None)
    vfile_collection_id: uuid.UUID | None = Field(default=None)
    vfile_upload_id: uuid.UUID | None = Field(default=None)
    summary_id: uuid.UUID | None = Field(default=None)
    summary_ids: list[uuid.UUID] = Field(default_factory=list)
    embedding_ids: list[uuid.UUID] = Field(default_factory=list)


class EmbeddingWorkflowInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(validate_assignment=True)
    vfile_id: uuid.UUID | None = Field(default=None)
    subject_id: str | None = Field(default=None)
    subject_type: str | None = Field(default=None)
    config: SplitterConfig = Field(default_factory=SplitterConfig)

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.vfile_id is None and self.subject_id is None:
            raise ValueError("vfile_id or subject_id + subject_type is required")
        return self


class EmbeddingRequest(BaseModel):
    embedding_id: uuid.UUID = Field(...)
    status: str = Field(default="")


class Job(BaseModel):
    uuid: str = Field(...)
    name: str = Field(...)
    status: str | None = Field(default=None)
    result: dict[str, Any] = Field(default={})


class JobList(BaseModel):
    jobs: list[Job] = Field([])


class AsyncResponse(BaseModel):
    payload: JobList = Field(default=JobList(jobs=[]))
    signature: str | None = Field(default=None)

    def gen_signature(self):
        self.signature = hmac.new(self.secret_key, self.payload.model_dump_json().encode(), hashlib.sha256).hexdigest()
        return self.signature

    def check_signature(self):
        expect = hmac.new(self.secret_key, self.payload.model_dump_json().encode(), hashlib.sha256).hexdigest()
        return expect != self.signature

    @property
    def secret_key(self):
        return b"NhqPtmfle3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j"


class WithContentMode(StrEnum):
    FULL = "full"
    CHUNK = "chunk"
    SUMMARY = "summary"
    NONE = "none"


class WithContent(BaseModel):
    mode: WithContentMode = Field(default=WithContentMode.FULL)
    chunk_id: uuid.UUID | None = Field(default=None)
    vfile_id: uuid.UUID | None = Field(default=None)

    # @model_validator(mode='after')
    # def check_model(self) -> Self:
    #     if self.chunk_id is None and self.mode == WithContentMode.CHUNK:
    #         raise ValueError("chunk_id is required for CHUNK mode")
    #     if self.vfile_id is None and self.mode in [WithContentMode.FULL, WithContentMode.SUMMARY]:
    #         raise ValueError("vfile_id is required for FULL or SUMMARY mode")
    #     return self


class Content(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(default="")
    verbatim: str = Field(default="", serialization_alias=("full"))
    chunk: str = Field(default="")
    title: str = Field(default="")
    description: str = Field(default="", serialization_alias=("descr"))
    keywords: list[str] = Field(default_factory=list, serialization_alias=("tags"))
    language: str = Field(default="", serialization_alias=("lang"))
    mode: WithContentMode = Field(default=WithContentMode.SUMMARY)
    summary_variant: str = Field(
        default="pretty", description="The summary variant to retrieved", serialization_alias=("svar")
    )

    def content(self):
        if self.mode == WithContentMode.FULL:
            return self.verbatim
        elif self.mode == WithContentMode.CHUNK:
            return self.chunk
        elif self.mode == WithContentMode.SUMMARY:
            return self.summary
        return ""

    def __str__(self):
        return self.content()


class SearchRecord(BaseModel):
    id: str | None = Field(default=None)
    vfile_id: str | uuid.UUID | None = Field(default=None)
    chunk_id: str | uuid.UUID | None = Field(default=None)
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_vfile(cls, vfile: VFileSchema):
        payload = {
            "subject_id": vfile.subject_id,
            "subject_type": vfile.subject_type,
            "created_at": vfile.source_created_at,
            "source": vfile.source,
            "content_type": vfile.source_content_type,
            "filename": vfile.source_filename,
            "file_id": str(vfile.id),
            "metadata": vfile.info,
        }
        return cls(id=str(vfile.id), vfile_id=str(vfile.id), payload=payload)


class OrderEnum(StrEnum):
    ASC = "asc"
    DESC = "desc"


class DocsQuery(BaseModel):
    limit: int = Field(100, description="The limit of the search results")
    mode: WithContentMode = Field(
        WithContentMode.SUMMARY, description="Return either the matching chunks, summary or full content"
    )
    vectordb: ManagerEnum = Field(default=ManagerEnum.NONE, description="vectordb to use")
    keys: Sequence[tuple[str, str]] | None = Field(default=None, description="The keys to return")
    collection_id: uuid.UUID | None = Field(default=None, description="The collection ID")
    collection_name: str | None = Field(default=None, description="collection name")
    ids: Sequence[tuple[str, str]] | None = Field(
        default=None, description="The ids to search, e.g [['doc', '123'], ['email', '456']]"
    )
    output: OutputFormatEnum = Field(OutputFormatEnum.JSON, description="The format to return the search results")
    date_lt: datetime.datetime | None = Field(default=None, description="The date to search before")
    date_gt: datetime.datetime | None = Field(default=None, description="The date to search after")
    filters: dict[str, Any] | None = Field(default=None)
    order: OrderEnum | None = Field(default=OrderEnum.ASC, description="The order of the search results")
    summary_variant: str = Field("default", description="The summary variant to retrieve if mode is SUMMARY")  # Added


class SearchQuery(DocsQuery):
    limit: int = Field(40, description="The limit of the search results")
    query: str = Field(..., description="The search query")
    language: str = Field("", description="The language to translate to the search query")


class DocsResponse(BaseModel):
    docs: list[Content] = Field(default_factory=list)
    query: DocsQuery
