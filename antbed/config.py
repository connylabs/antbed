# pylint: disable=no-self-argument
import logging
import logging.config
from typing import Any

import ant31box.config
from activealchemy.config import PostgreSQLConfigSchema
from ant31box.config import BaseConfig, FastAPIConfigSchema, GConfig, LoggingConfigSchema
from antgent.config import AgentsConfigSchema, AliasesSchema, LLMsConfigSchema
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from temporalloop.config import TemporalSettings as TemporalConfigSchema
from temporalloop.config import WorkerSettings as WorkerConfigSchema
from temporalloop.schedule import Schedule as TemporalScheduleSchema

LOGGING_CONFIG: dict[str, Any] = ant31box.config.LOGGING_CONFIG
LOGGING_CONFIG["loggers"].update({"antbed": {"handlers": ["default"], "level": "INFO", "propagate": True}})

logger: logging.Logger = logging.getLogger("antbed")


class LoggingCustomConfigSchema(LoggingConfigSchema):
    log_config: dict[str, Any] | str | None = Field(default_factory=lambda: LOGGING_CONFIG)


class FastAPIConfigCustomSchema(FastAPIConfigSchema):
    server: str = Field(default="antbed.server.server:serve")


class LogfireConfigSchema(BaseConfig):
    token: str = Field(default="")


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


class AntbedConfigSchema(BaseConfig):
    postgresql: PostgreSQLConfigSchema = Field(default_factory=PostgreSQLConfigSchema)


class TemporalCustomConfigSchema(TemporalConfigSchema):
    workers: list[WorkerConfigSchema] = Field(
        default=[
            WorkerConfigSchema(
                name="antbed-activities",
                queue="antbed-queue-activity",
                activities=[
                    "antbed.temporal.activities:echo",
                    "antgent.workflows.summarizer:run_summarizer_one_type_activity",
                ],
                workflows=[],
            ),
            WorkerConfigSchema(
                name="antbed-workflow",
                queue="antbed-queue",
                activities=[],
                workflows=[
                    "antbed.temporal.workflows.echo:EchoWorkflow",
                    "antgent.workflows.summarizer:TextSummarizerOneTypeWorkflow",
                    "antgent.workflows.summarizer:TextSummarizerAllWorkflow",
                ],
            ),
        ],
    )
    converter: str | None = Field(default="temporalio.contrib.pydantic:pydantic_data_converter")
    # default="temporalloop.converters.pydantic:pydantic_data_converter")


ENVPREFIX = "ANTBED"


# Main configuration schema
class ConfigSchema(ant31box.config.ConfigSchema):
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
    logfire: LogfireConfigSchema = Field(default_factory=LogfireConfigSchema)
    llms: LLMsConfigSchema = Field(default_factory=LLMsConfigSchema)
    agents: AgentsConfigSchema = Field(default_factory=AgentsConfigSchema)
    aliases: AliasesSchema = Field(default_factory=AliasesSchema)


class Config(ant31box.config.Config[ConfigSchema]):
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
    def logfire(self) -> LogfireConfigSchema:
        return self.conf.logfire

    @property
    def temporalio(self) -> TemporalCustomConfigSchema:
        return self.conf.temporalio

    @property
    def schedules(self) -> dict[str, TemporalScheduleSchema]:
        return self.conf.schedules

    @property
    def llms(self) -> LLMsConfigSchema:
        return self.conf.llms

    @property
    def agents(self) -> AgentsConfigSchema:
        return self.conf.agents

    @property
    def aliases(self) -> AliasesSchema:
        return self.conf.aliases


def config(path: str | None = None, reload: bool = False) -> Config:
    GConfig[Config].set_conf_class(Config)
    if reload:
        GConfig[Config].reinit()
    # load the configuration
    GConfig[Config](path)
    # Return the instance of the configuration
    return GConfig[Config].instance()
