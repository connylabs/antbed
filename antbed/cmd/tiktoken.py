import json
from typing import Annotated

import tiktoken
import typer
from ant31box.cmd.typer.models import OutputEnum


def tikcount(
    output: Annotated[
        OutputEnum,
        typer.Option("--output", "-o", help="Output format."),
    ] = OutputEnum.json,
) -> None:
    """Counts tokens from stdin."""
    stdin_text = typer.get_text_stream("stdin")
    model = "gpt-4o"
    encoder = tiktoken.encoding_for_model(model)
    res = {"tokens": len(encoder.encode(stdin_text.read())), "model": model}
    if output == "json":
        typer.echo(json.dumps(res, indent=2))
    else:
        typer.echo(res["tokens"])
    raise typer.Exit()
