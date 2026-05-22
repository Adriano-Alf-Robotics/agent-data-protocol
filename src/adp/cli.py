"""Command-line interface for ADP.

Usage:
    adp encode      JSON stdin -> ADP stdout
    adp decode      ADP stdin -> JSON stdout
    adp to-md       ADP stdin -> Markdown stdout
    adp validate    ADP stdin -> exit 0 if valid, 1 if not
    adp bench       JSON stdin -> token comparison table
    adp prompt      Print the ADP system prompt
"""

from __future__ import annotations

import json
import sys

import click

from adp.parser import decode, ADPParseError
from adp.serializer import encode
from adp.converters import to_json, from_json, to_markdown
from adp.prompt import system_prompt, few_shot_block


@click.group()
@click.version_option()
def main() -> None:
    """ADP — token-efficient lossless format for AI agent communication."""


@main.command("encode")
@click.option("--no-tables", is_flag=True, help="Disable automatic table compression")
def cmd_encode(no_tables: bool) -> None:
    """Read JSON from stdin, write ADP to stdout."""
    raw = sys.stdin.read()
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise click.ClickException("top-level JSON must be an object")
    sys.stdout.write(encode(obj, prefer_tables=not no_tables))


@main.command("decode")
@click.option("--indent", type=int, default=2, help="JSON indent")
def cmd_decode(indent: int) -> None:
    """Read ADP from stdin, write JSON to stdout."""
    raw = sys.stdin.read()
    try:
        sys.stdout.write(to_json(raw, indent=indent))
        sys.stdout.write("\n")
    except ADPParseError as e:
        raise click.ClickException(f"ADP parse error: {e}")


@main.command("to-md")
def cmd_to_md() -> None:
    """Read ADP from stdin, write Markdown to stdout."""
    raw = sys.stdin.read()
    try:
        sys.stdout.write(to_markdown(raw))
    except ADPParseError as e:
        raise click.ClickException(f"ADP parse error: {e}")


@main.command("validate")
def cmd_validate() -> None:
    """Read ADP from stdin, exit 0 if valid, 1 otherwise."""
    raw = sys.stdin.read()
    try:
        decode(raw)
        click.echo("OK", err=True)
    except ADPParseError as e:
        click.echo(f"INVALID: {e}", err=True)
        sys.exit(1)


@main.command("bench")
@click.option("--tokenizer", default="cl100k_base",
              help="tiktoken encoding name (e.g. cl100k_base, o200k_base)")
def cmd_bench(tokenizer: str) -> None:
    """Read JSON from stdin, compare token counts JSON vs ADP."""
    try:
        import tiktoken
    except ImportError:
        raise click.ClickException(
            "tiktoken not installed. Install with: uv sync --all-extras"
        )
    raw = sys.stdin.read()
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise click.ClickException("top-level JSON must be an object")
    adp_str = encode(obj)
    json_str = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    json_pretty = json.dumps(obj, ensure_ascii=False, indent=2)
    enc = tiktoken.get_encoding(tokenizer)
    n_adp = len(enc.encode(adp_str))
    n_json_min = len(enc.encode(json_str))
    n_json_pretty = len(enc.encode(json_pretty))
    click.echo(f"Tokenizer:        {tokenizer}")
    click.echo(f"ADP tokens:       {n_adp:>6d}  ({len(adp_str)} bytes)")
    click.echo(f"JSON minified:    {n_json_min:>6d}  ({len(json_str)} bytes)")
    click.echo(f"JSON pretty:      {n_json_pretty:>6d}  ({len(json_pretty)} bytes)")
    if n_json_min > 0:
        delta_min = (n_json_min - n_adp) / n_json_min * 100
        click.echo(f"ADP vs minified:  {delta_min:+.1f}% (saving)")
    if n_json_pretty > 0:
        delta_pretty = (n_json_pretty - n_adp) / n_json_pretty * 100
        click.echo(f"ADP vs pretty:    {delta_pretty:+.1f}% (saving)")


@main.command("prompt")
@click.option("--few-shot", is_flag=True, help="Append few-shot examples")
def cmd_prompt(few_shot: bool) -> None:
    """Print the ADP system prompt for LLM agents."""
    out = system_prompt()
    if few_shot:
        out += "\n\n" + few_shot_block()
    click.echo(out)


if __name__ == "__main__":
    main()
