import os
from pathlib import Path
import typer
from aptitude import llm  # noqa  (registers providers)
from aptitude.models import Source
from aptitude.config import resolve_config, default_provider
from aptitude.llm.factory import build_provider
from aptitude.llm.base import provider_registry
from aptitude.export.base import export_registry
import aptitude.export.generic_prompt, aptitude.export.local_llm  # noqa
import aptitude.export.mcp_manifest, aptitude.export.packager  # noqa
import aptitude.ingest.pdf, aptitude.ingest.epub  # noqa  (registers ingestion adapters)
import aptitude.ingest.web, aptitude.ingest.github  # noqa
from aptitude.pipeline import RunConfig, run
from aptitude.validate.validator import validate_skill_dir
from aptitude.errors import AptitudeError

app = typer.Typer(help="Aptitude — generate skills from artifacts.")

def _read_prompt(p: str) -> str:
    return Path(p[1:]).read_text(encoding="utf-8") if p.startswith("@") else p

@app.command()
def create(prompt: str = typer.Option(..., "--prompt", "-p"),
           input: list[str] = typer.Option([], "--input", "-i"),
           type: str = typer.Option("auto", "--type"),
           provider: str = typer.Option(None, "--provider"),
           model: str = typer.Option(None, "--model"),
           format: str = typer.Option("claude-skill", "--format"),
           out: str = typer.Option("./out", "--out"),
           budget: int = typer.Option(6000, "--budget"),
           dry_run: bool = typer.Option(False, "--dry-run"),
           verbose: bool = typer.Option(False, "-v")):
    env = dict(os.environ)
    cfg = resolve_config({"provider": provider, "model": model}, env,
                         Path("aptitude.toml"))
    prov_name = cfg["provider"] or default_provider(env)
    fmts = (export_registry.names() if format == "all"
            else [f.strip() for f in format.split(",")])
    try:
        provider_obj = build_provider(prov_name, cfg, env)
        rc = RunConfig(prompt=_read_prompt(prompt),
                       sources=[Source(i, type) for i in input],
                       provider=prov_name, model=cfg.get("model"), formats=fmts,
                       out=Path(out), budget=budget, dry_run=dry_run)
        res = run(rc, provider_obj)
    except AptitudeError as e:
        typer.echo(f"error: {e}"); raise typer.Exit(2)
    for raw, why in res.skipped:
        typer.echo(f"skipped {raw}: {why}")
    if res.corpus is not None:
        typer.echo(res.corpus[:2000])
    elif res.draft:
        typer.echo(f"created '{res.draft.name}' → {len(res.written)} files in {out}")
        for w in res.warnings:
            typer.echo(f"warning: {w}")
    raise typer.Exit(res.exit_code)

@app.command()
def providers():
    env = os.environ
    from aptitude.config import api_key_for
    for name in provider_registry.names():
        state = "ready" if (name in ("ollama", "fake") or api_key_for(name, env)) else "no key"
        typer.echo(f"{name}: {state}")

@app.command()
def formats():
    for name in export_registry.names():
        typer.echo(name)

@app.command()
def validate(path: str):
    try:
        warns = validate_skill_dir(Path(path))
    except AptitudeError as e:
        typer.echo(f"invalid: {e}"); raise typer.Exit(2)
    typer.echo("valid" + ("" if not warns else f" (warnings: {warns})"))

@app.command()
def init():
    p = Path("aptitude.toml")
    if p.exists():
        typer.echo("aptitude.toml already exists"); raise typer.Exit(1)
    p.write_text('provider = "ollama"\nmodel = "llama3.1"\nformat = "claude-skill"\n', encoding="utf-8")
    typer.echo("wrote aptitude.toml")
