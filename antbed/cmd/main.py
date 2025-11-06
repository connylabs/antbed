#!/usr/bin/env python3
import typer
from ant31box.cmd.typer.default_config import app as default_config_app
from ant31box.cmd.typer.version import app as version_app

from antbed.config import config
from antbed.version import VERSION

from .server import app as server_app
from .tiktoken import tikcount
from .worker import app as looper_app

app = typer.Typer(no_args_is_help=True)

# looper_cmd = typer.Typer(
#     name="looper",
#     help="Starts the temporal worker.",
#     context_settings={
#         "auto_envvar_prefix": "TEMPORALRUNNER",
#         "allow_extra_args": True,
#         "ignore_unknown_options": True,
#     },
# )


# @looper_cmd.callback(invoke_without_command=True)
# def looper_wrapper(ctx: typer.Context):
#     """Wrapper to initialize before starting the looper."""
#     _config = config()
#     init(_config.conf, mode="worker")
#     looper_main(ctx, config=None)


# Register all sub-commands at module level
app.add_typer(looper_app)
app.add_typer(server_app)
app.add_typer(version_app)
app.add_typer(default_config_app)
app.command(name="tikcount")(tikcount)


def main() -> None:
    """Main entry point for the CLI."""
    # Initialize config and version
    _ = config()
    _ = VERSION.app_version

    # Parse cmd-line arguments and options
    # pylint: disable=no-value-for-parameter
    app()


if __name__ == "__main__":
    main()
