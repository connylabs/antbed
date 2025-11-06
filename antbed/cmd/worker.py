from pathlib import Path
from typing import Annotated

import typer
from temporalloop.cmd import looper as looper_cmd
from temporalloop.cmd import scheduler as scheduler_cmd
from temporalloop.cmd.models import LogLevel

from antbed.config import config
from antbed.init import init

app = typer.Typer(no_args_is_help=True)


@app.command(
    name="looper",
    help="Starts the temporal worker.",
    context_settings={
        "auto_envvar_prefix": "TEMPORALRUNNER",
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
def looper_wrapper(  # pylint: disable=too-many-arguments
    ctx: typer.Context,
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
    namespace: Annotated[
        str | None,
        typer.Option(
            "--namespace",
            "-n",
            help="temporalio namespace",
            show_default=True,
        ),
    ] = None,
    host: Annotated[
        str | None,
        typer.Option("--host", help="Address of the Temporal Frontend", show_default=True),
    ] = None,
    queue: Annotated[
        str | None,
        typer.Option("--queue", "-q", help="Queue to listen on", show_default=True),
    ] = None,
    workflow: Annotated[
        list[str] | None,
        typer.Option(
            "--workflow",
            "-w",
            help="Workflow managed by the worker: python.module:WorkflowClass. Repeat for more workflows.",
        ),
    ] = None,
    activity: Annotated[
        list[str] | None,
        typer.Option(
            "--activity",
            "-a",
            help="Activity: python.module:activity_function. Repeat for more activities.",
        ),
    ] = None,
    interceptor: Annotated[
        list[str] | None,
        typer.Option(
            "--interceptor",
            "-i",
            help="Interceptor class to add: python.module:InterceptorClass. Repeat for more interceptors.",
        ),
    ] = None,
    log_config: Annotated[
        Path | None,
        typer.Option(
            "--log-config",
            exists=True,
            help="Logging configuration file. Supported formats: .ini, .json, .yaml.",
            show_default=True,
        ),
    ] = None,
    log_level: Annotated[
        LogLevel,
        typer.Option(
            "--log-level",
            help="Log level.",
            show_default=True,
            case_sensitive=False,
        ),
    ] = LogLevel.info,
    use_colors: Annotated[
        bool,
        typer.Option(
            "--use-colors/--no-use-colors",
            help="Enable/Disable colorized logging.",
        ),
    ] = True,
):
    """Wrapper to initialize before starting the looper."""
    from temporalio.worker import SandboxedWorkflowRunner
    from temporalio.worker.workflow_sandbox import SandboxRestrictions
    
    _config = config(str(config_path) if config_path else None)
    init(_config.conf, mode="worker")

    # Configure passthrough modules for Temporal sandbox to avoid restrictions
    # on non-deterministic imports used only in activities
    passthrough = [
        "antgent",
        "litellm",
        "httpx",
        "urllib",
        "urllib.request", 
        "http",
        "http.client",
    ]
    
    # Create custom workflow runner with passthrough modules
    custom_runner = SandboxedWorkflowRunner(
        restrictions=SandboxRestrictions.passthrough_modules(*passthrough)
    )
    
    # Store in context for temporalloop to use
    ctx.obj = ctx.obj or {}
    ctx.obj["workflow_runner"] = custom_runner

    # Call the original looper main function with all arguments from the context
    looper_cmd.main(
        ctx,
        config=config_path,
        namespace=namespace,
        host=host,
        queue=queue,
        workflow=workflow,
        activity=activity,
        interceptor=interceptor,
        log_config=log_config,
        log_level=log_level,
        use_colors=use_colors,
    )


app.command(
    name="scheduler",
    help="Starts the temporal scheduler.",
    context_settings={"auto_envvar_prefix": "TEMPORALRUNNER"},
)(scheduler_cmd.scheduler)
