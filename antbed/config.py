# pylint: disable=no-self-argument
import logging
import logging.config
from typing import Any

import ant31box.config
from activealchemy.config import PostgreSQLConfigSchema
from ant31box.config import BaseConfig, FastAPIConfigSchema, GConfig, LoggingConfigSchema
from ant31box.config import Config as Ant31BoxConfig
from antgent.aliases import AliasResolver
from antgent.config import AliasesSchema, AntgentConfig, LLMsConfigSchema, TracesConfigSchema
from antgent.config import ConfigSchema as AntgentConfigSchema
from antgent.models.agent import AgentConfig, ModelProvidersConfig, ProviderMapping, ProviderSettings
from pydantic import Field, RootModel, field_validator
from pydantic_settings import SettingsConfigDict
from temporalloop.config import TemporalSettings as TemporalConfigSchema
from temporalloop.config import WorkerSettings as WorkerConfigSchema
from temporalloop.schedule import Schedule as TemporalScheduleSchema

LOGGING_CONFIG: dict[str, Any] = ant31box.config.LOGGING_CONFIG
LOGGING_CONFIG["loggers"].update({"antbed": {"handlers": ["default"], "level": "INFO", "propagate": True}})

logger: logging.Logger = logging.getLogger("antbed")


DEFAULT_ALIASES = {
    "strong": "gemini/gemini-pro",
    "weak": "gemini/gemini-flash",
}

DEFAULT_MODEL_PROVIDERS = ModelProvidersConfig(
    default=ProviderSettings(client="litellm", api_mode="chat"),
    mappings=[
        ProviderMapping(prefix="gemini", client="litellm", api_mode="chat"),
        ProviderMapping(prefix="gpt-", client="openai", api_mode="response"),
        ProviderMapping(prefix="openai/", client="openai", api_mode="response"),
    ],
)


DEFAULT_AGENTS_CONFIG: dict[str, AgentConfig] = {}


class AgentsCustomConfigSchema(RootModel[dict[str, AgentConfig]]):
    pass


class LoggingCustomConfigSchema(LoggingConfigSchema):
    log_config: dict[str, Any] | str | None = Field(default_factory=lambda: LOGGING_CONFIG)


class FastAPIConfigCustomSchema(FastAPIConfigSchema):
    server: str = Field(default="antbed.server.server:serve")


class QdrantConfigSchema(BaseConfig):
    host: str = Field(default="localhost")
    prefer_grpc: bool = Field(default=True)
    api_key: str | None = Field(default=None)
    port: int = Field(default=6333)
    grpc_port: int = Field(default=6334)
    https: bool = Field(default=False)


class OpenAIProjectKeySchema(BaseConfig):
    api_key: str = Field(default="antbed-openaiKEY")
    project_id: str = Field(default="proj-1xZoR")
    name: str = Field(default="default")
    url: str | None = Field(default=None)


class OpenAIConfigSchema(BaseConfig):
    organization: str = Field(default="Ant31")
    organization_id: str = Field(default="org-1xZoRaUM")
    url: str | None = Field(default=None)
    projects: list[OpenAIProjectKeySchema] = Field(
        default=[
            OpenAIProjectKeySchema(
                api_key="antbed-openaiKEY",
                project_id="proj_OIMUS8HgaQZ",
                name="Default",
            ),
            OpenAIProjectKeySchema(
                api_key="antbed-openaiKEY",
                project_id="proj_NrZHbXS1CDXh",
                name="AskMyCase",
            ),
        ]
    )

    def get_project(self, name: str) -> OpenAIProjectKeySchema | None:
        for project in self.projects:
            if project.name.lower() == name.lower():
                return project
        return None


class EmbeddingProviderConfig(BaseConfig):
    """Configuration for a single embedding provider"""

    name: str = Field(..., description="Provider name (e.g., 'openai', 'cohere', 'voyage')")
    api_key: str | None = Field(default=None, description="API key for this provider")
    api_key_ref: str | None = Field(default=None, description="Reference to llm provider key (e.g., 'llms.openai')")
    base_url: str | None = Field(default=None, description="Custom API base URL")
    organization_id: str | None = Field(default=None, description="Organization ID (OpenAI specific)")
    project_id: str | None = Field(default=None, description="Project ID (OpenAI specific)")
    default_model: str = Field(default="text-embedding-3-large", description="Default model for this provider")
    models: dict[str, str] = Field(
        default_factory=dict,
        description="Model aliases (e.g., 'large': 'text-embedding-3-large')",
    )

    @field_validator("api_key_ref", "api_key")
    @classmethod
    def check_key_config(cls, v, info):
        """Ensure either api_key or api_key_ref is provided"""
        if info.field_name == "api_key" and v is None:
            values = info.data
            if values.get("api_key_ref") is None:
                raise ValueError("Either api_key or api_key_ref must be provided")
        return v


class EmbeddingsConfigSchema(BaseConfig):
    """Configuration for embedding providers"""

    providers: dict[str, EmbeddingProviderConfig] = Field(
        default_factory=lambda: {
            "openai": EmbeddingProviderConfig(
                name="openai",
                api_key_ref="llms.openai",
                default_model="text-embedding-3-large",
                models={"large": "text-embedding-3-large", "small": "text-embedding-3-small"},
            )
        }
    )
    default_provider: str = Field(default="openai", description="Default provider to use for embeddings")

    def get_provider(self, name: str | None = None) -> EmbeddingProviderConfig:
        """Get provider config by name, falls back to default"""
        provider_name = name or self.default_provider
        if provider_name not in self.providers:
            raise ValueError(f"Embedding provider '{provider_name}' not found in config")
        return self.providers[provider_name]


class AntbedConfigSchema(BaseConfig):
    postgresql: PostgreSQLConfigSchema = Field(default_factory=PostgreSQLConfigSchema)


class TemporalCustomConfigSchema(TemporalConfigSchema):
    workers: list[WorkerConfigSchema] = Field(
        default=[
            WorkerConfigSchema(
                name="antbed-worker",
                queue="antbed-queue",
                activities=[
                    "antbed.temporal.activities:echo",
                    "antbed.temporal.activities:aecho",
                    "antbed.temporal.activities:get_vfile_id",
                    "antbed.temporal.activities:get_or_create_file",
                    "antbed.temporal.activities:get_or_create_split",
                    "antbed.temporal.activities:embedding",
                    "antbed.temporal.activities:vfile_has_summaries",
                    "antbed.temporal.activities:add_vfile_to_collection",
                    "antbed.temporal.activities:add_vfile_to_vector",
                    "antbed.temporal.activities:save_summaries_to_db",
                    "antgent.workflows.summarizer.text:run_summarizer_one_type_activity",
                ],
                workflows=[
                    "antbed.temporal.workflows.echo:EchoWorkflow",
                    "antbed.temporal.workflows.upload:UploadWorkflow",
                    "antbed.temporal.workflows.embedding:EmbeddingWorkflow",
                    "antgent.workflows.summarizer.text:TextSummarizerAllWorkflow",
                ],
            ),
        ],
    )
    converter: str | None = Field(default="temporalio.contrib.pydantic:pydantic_data_converter")
    # default="temporalloop.converters.pydantic:pydantic_data_converter")


ENVPREFIX = "ANTBED"


# Main configuration schema
class ConfigSchema(AntgentConfigSchema):
    model_config = SettingsConfigDict(
        env_prefix=f"{ENVPREFIX}_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="allow",
    )
    antbed: AntbedConfigSchema = Field(default_factory=AntbedConfigSchema)
    name: str = Field(default="antbed")
    openai: OpenAIConfigSchema = Field(default_factory=OpenAIConfigSchema, exclude=True)
    qdrant: QdrantConfigSchema = Field(default_factory=QdrantConfigSchema)
    logging: LoggingConfigSchema = Field(default_factory=LoggingCustomConfigSchema)
    server: FastAPIConfigSchema = Field(default_factory=FastAPIConfigCustomSchema)
    temporalio: TemporalCustomConfigSchema = Field(default_factory=TemporalCustomConfigSchema)
    schedules: dict[str, TemporalScheduleSchema] = Field(default_factory=dict)
    llms: LLMsConfigSchema = Field(default_factory=LLMsConfigSchema)
    model_providers: ModelProvidersConfig = Field(default_factory=lambda: DEFAULT_MODEL_PROVIDERS)
    agents: AgentsCustomConfigSchema = Field(
        default_factory=lambda: AgentsCustomConfigSchema(root=DEFAULT_AGENTS_CONFIG)
    )
    traces: TracesConfigSchema = Field(default_factory=TracesConfigSchema)
    aliases: AliasesSchema = Field(default_factory=lambda: AliasesSchema(root=AliasResolver(DEFAULT_ALIASES)))
    embeddings: EmbeddingsConfigSchema = Field(default_factory=EmbeddingsConfigSchema)


class Config(AntgentConfig[ConfigSchema], Ant31BoxConfig[ConfigSchema]):
    _env_prefix = ENVPREFIX
    __config_class__: type[ConfigSchema] = ConfigSchema

    @property
    def openai(self) -> OpenAIConfigSchema:
        return self.conf.openai

    @property
    def antbed(self) -> AntbedConfigSchema:
        return self.conf.antbed

    @property
    def qdrant(self) -> QdrantConfigSchema:
        return self.conf.qdrant

    @property
    def llms(self) -> LLMsConfigSchema:
        return self.conf.llms

    @property
    def agents(self) -> dict[str, AgentConfig]:
        return self.conf.agents.root

    @property
    def embeddings(self) -> EmbeddingsConfigSchema:
        return self.conf.embeddings


def config(path: str | None = None, reload: bool = False) -> Config:
    GConfig[Config].set_conf_class(Config)
    if reload:
        GConfig[Config].reinit()
    # load the configuration
    GConfig[Config](path)
    # Return the instance of the configuration
    return GConfig[Config].instance()
