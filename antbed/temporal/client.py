from temporalio.client import Client
from temporalloop.converters.pydantic import pydantic_data_converter

from antbed.config import TemporalCustomConfigSchema, config

TEMPORAL_CLIENT: Client | None = None


async def tclient(conf: TemporalCustomConfigSchema | None = None) -> Client:
    return await GTClient(conf).client()


class TClient:
    def __init__(self, conf: TemporalCustomConfigSchema | None = None) -> None:
        if conf is None:
            conf = config().temporalio

        self.conf: TemporalCustomConfigSchema = conf
        self._client = None

    def set_client(self, client: Client) -> None:
        self._client = client

    async def client(self) -> Client:
        if self._client is None:
            self._client = await Client.connect(
                self.conf.host,
                namespace=self.conf.namespace,
                lazy=True,
                data_converter=pydantic_data_converter,
            )
        return self._client


class GTClient:
    _instance: TClient | None = None

    def __new__(cls, conf: TemporalCustomConfigSchema | None = None) -> TClient:
        if cls._instance is None:
            cls._instance = TClient(conf)
        return cls._instance

    @classmethod
    def reinit(cls) -> None:
        cls._instance = None
