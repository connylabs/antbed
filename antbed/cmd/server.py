#!/usr/bin/env python3
import enum
import logging
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from ant31box.init import init

from antbed.config import Config
from antbed.config import config as confload

logger = logging.getLogger("ant31box.info")


class LogLevel(str, enum.Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    TRACE = "trace"


app = typer.Typer(no_args_is_help=True)


def run_server(config: Config):
    logger.info("Starting server")
    typer.echo(f"{config.server.model_dump()}")
    init(config.conf, "fastapi")
    uvicorn.run(
        config.server.server,
        host=config.server.host,
        port=config.server.port,
        log_level=config.logging.level,
        # log_config=config.logging.log_config,
        use_colors=config.logging.use_colors,
        reload=config.server.reload,
        factory=True,
    )


# pylint: disable=too-many-arguments
@app.command(context_settings={"auto_envvar_prefix": "FASTAPI"})
def server(
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            exists=True,
            help="Configuration file in YAML format.",
            show_default=True,
        ),
    ] = None,
    host: Annotated[
        str | None,
        typer.Option("--host", help="Address of the server", show_default=True),
    ] = None,
    port: Annotated[int | None, typer.Option("--port", help="Port to listen on")] = None,
    temporal_host: Annotated[
        str | None,
        typer.Option("--temporal-host", help="Address of the Temporal server", show_default=True),
    ] = None,
    use_colors: Annotated[
        bool,
        typer.Option(
            "--use-colors/--no-use-colors",
            help="Enable/Disable colorized logging.",
        ),
    ] = True,
    log_level: Annotated[
        LogLevel,
        typer.Option(
            "--log-level",
            help="Log level.",
            show_default=True,
            case_sensitive=False,
        ),
    ] = LogLevel.INFO,
    log_config: Annotated[
        Path | None,
        typer.Option(
            "--log-config",
            exists=True,
            help="Logging configuration file. Supported formats: .ini, .json, .yaml.",
            show_default=True,
        ),
    ] = None,
) -> None:
    """Starts the server."""
    _config = confload(str(config_path) if config_path else None)
    if host:
        _config.server.host = host
    if port:
        _config.server.port = port
    if temporal_host:
        _config.temporalio.host = temporal_host
    if log_level:
        _config.logging.level = log_level.value
    if log_config:
        _config.logging.log_config = str(log_config)
    if use_colors is not None:
        _config.logging.use_colors = use_colors

    run_server(_config)
