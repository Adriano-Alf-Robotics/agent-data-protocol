"""Command-line interface for GLA.

Usage:
    gla encode      JSON stdin -> GLA stdout
    gla decode      GLA stdin -> JSON stdout
    gla to-md       GLA stdin -> Markdown stdout
    gla validate    GLA stdin -> exit 0 if valid, 1 if not
    gla bench       JSON stdin -> token comparison table
    gla prompt      Print the GLA system prompt
"""

from __future__ import annotations

import json
import sys
from typing import Optional

import click

from gla.parser import decode, GLAParseError
from gla.serializer import encode
from gla.converters import to_json, from_json, to_markdown
from gla.prompt import system_prompt, few_shot_block


@click.group()
@click.version_option()
def main() -> None:
    """GLA — Goal Language Agents. Token-efficient lossless format for AI agents."""


@main.command("encode")
@click.option("--no-tables", is_flag=True, help="Disable automatic table compression")
def cmd_encode(no_tables: bool) -> None:
    """Read JSON from stdin, write GLA to stdout."""
    raw = sys.stdin.read()
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise click.ClickException("top-level JSON must be an object")
    sys.stdout.write(encode(obj, prefer_tables=not no_tables))


@main.command("decode")
@click.option("--indent", type=int, default=2, help="JSON indent")
def cmd_decode(indent: int) -> None:
    """Read GLA from stdin, write JSON to stdout."""
    raw = sys.stdin.read()
    try:
        sys.stdout.write(to_json(raw, indent=indent))
        sys.stdout.write("\n")
    except GLAParseError as e:
        raise click.ClickException(f"GLA parse error: {e}")


@main.command("to-md")
def cmd_to_md() -> None:
    """Read GLA from stdin, write Markdown to stdout."""
    raw = sys.stdin.read()
    try:
        sys.stdout.write(to_markdown(raw))
    except GLAParseError as e:
        raise click.ClickException(f"GLA parse error: {e}")


@main.command("validate")
def cmd_validate() -> None:
    """Read GLA from stdin, exit 0 if valid, 1 otherwise."""
    raw = sys.stdin.read()
    try:
        decode(raw)
        click.echo("OK", err=True)
    except GLAParseError as e:
        click.echo(f"INVALID: {e}", err=True)
        sys.exit(1)


@main.command("bench")
@click.option("--tokenizer", default="cl100k_base",
              help="tiktoken encoding name (e.g. cl100k_base, o200k_base)")
def cmd_bench(tokenizer: str) -> None:
    """Read JSON from stdin, compare token counts JSON vs GLA."""
    try:
        import tiktoken
    except ImportError:
        raise click.ClickException(
            "tiktoken not installed. Install with: uv pip install tiktoken"
        )
    raw = sys.stdin.read()
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise click.ClickException("top-level JSON must be an object")
    gla_str = encode(obj)
    json_str = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    json_pretty = json.dumps(obj, ensure_ascii=False, indent=2)
    enc = tiktoken.get_encoding(tokenizer)
    n_gla = len(enc.encode(gla_str))
    n_json_min = len(enc.encode(json_str))
    n_json_pretty = len(enc.encode(json_pretty))
    click.echo(f"Tokenizer:        {tokenizer}")
    click.echo(f"GLA tokens:       {n_gla:>6d}  ({len(gla_str)} bytes)")
    click.echo(f"JSON minified:    {n_json_min:>6d}  ({len(json_str)} bytes)")
    click.echo(f"JSON pretty:      {n_json_pretty:>6d}  ({len(json_pretty)} bytes)")
    if n_json_min > 0:
        delta_min = (n_json_min - n_gla) / n_json_min * 100
        click.echo(f"GLA vs minified:  {delta_min:+.1f}% (saving)")
    if n_json_pretty > 0:
        delta_pretty = (n_json_pretty - n_gla) / n_json_pretty * 100
        click.echo(f"GLA vs pretty:    {delta_pretty:+.1f}% (saving)")


@main.command("prompt")
@click.option("--few-shot", is_flag=True, help="Append few-shot examples")
def cmd_prompt(few_shot: bool) -> None:
    """Print the GLA system prompt for LLM agents."""
    out = system_prompt()
    if few_shot:
        out += "\n\n" + few_shot_block()
    click.echo(out)


if __name__ == "__main__":
    main()
