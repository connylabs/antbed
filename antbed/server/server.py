from typing import ClassVar

from ant31box.server.server import Server, serve_from_config
from fastapi import FastAPI

from antbed.config import config
from antbed.init import init


class AntbedServer(Server):
    _routers: ClassVar[set[str]] = {
        "antbed.server.api.antbed:router",
        "antbed.server.api.search:router",
        "antbed.server.api.job_info:router",
        "antgent.server.api.workflows.summarizer:router",
    }
    _middlewares: ClassVar[set[str]] = {"tokenAuth"}


# override this method to use a different server class/config
def serve() -> FastAPI:
    app = serve_from_config(config(), AntbedServer)
    init(config().conf, mode="server", extra={"app": app})
    return app
