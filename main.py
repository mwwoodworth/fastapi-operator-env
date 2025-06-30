import json
import sys
import logging
from typing import List
import typer
from codex.brainops_operator import run_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False, context_settings={"allow_extra_args": True, "ignore_unknown_options": True})

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Run BrainOps tasks from the command line."""
    if not ctx.args:
        typer.echo("Usage: python main.py <task_name> --key value ...")
        raise typer.Exit(1)

    task = ctx.args[0]
    args = ctx.args[1:]
    it = iter(args)
    context = {}
    for arg in it:
        if not arg.startswith("--"):
            typer.echo(f"Invalid argument {arg}")
            raise typer.Exit(1)
        key = arg.lstrip("-")
        try:
            value = next(it)
        except StopIteration:
            typer.echo(f"Missing value for {arg}")
            raise typer.Exit(1)
        context[key] = value

    try:
        result = run_task(task, context)
        typer.echo(json.dumps(result, indent=2))
        raise typer.Exit(0)
    except Exception as exc:
        logger.error("Task failed: %s", exc)
        typer.echo(json.dumps({"status": "error", "message": str(exc)}))
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
