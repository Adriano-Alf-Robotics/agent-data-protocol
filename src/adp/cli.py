"""Command-line interface for ADP.

Usage:
    adp encode      JSON stdin -> ADP stdout
    adp decode      ADP stdin -> JSON stdout
    adp to-md       ADP stdin -> Markdown stdout
    adp validate    ADP stdin -> exit 0 if valid, 1 if not
    adp sign        ADP stdin -> ADP+integrity stdout
    adp verify      ADP+integrity stdin -> ADP stdout (exit 1 if tampered)
    adp bench       JSON stdin -> token comparison table
    adp prompt      Print the ADP system prompt
"""

from __future__ import annotations

import json
import sys

import click

from adp.parser import decode, ADPParseError
from adp.serializer import encode
from adp.converters import to_json, from_json, to_markdown, to_html
from adp.prompt import system_prompt, few_shot_block
from adp.integrity import sign as integrity_sign, verify as integrity_verify, is_signed, strip as integrity_strip, IntegrityError


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


@main.command("to-html")
@click.option("--title", default="ADP document", help="HTML page title")
@click.option("--fragment", is_flag=True, help="Emit only inner content (no <!DOCTYPE> wrapper)")
def cmd_to_html(title: str, fragment: bool) -> None:
    """Read ADP from stdin, write a standalone HTML page to stdout."""
    raw = sys.stdin.read()
    try:
        sys.stdout.write(to_html(raw, title=title, standalone=not fragment))
    except ADPParseError as e:
        raise click.ClickException(f"ADP parse error: {e}")


@main.command("serve")
@click.option("--port", default=8765, help="HTTP port (default 8765)")
@click.option("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
@click.option("--title", default="ADP live stream", help="Page title")
def cmd_serve(port: int, host: str, title: str) -> None:
    """Start a live HTML viewer: reads ADP records from stdin, appends them to
    a single web page that auto-updates via Server-Sent Events.

    Esempio:
        my-agent-producing-adp | uv run adp serve --port 8000
        # Apri http://localhost:8000 in un browser
    """
    from adp.serve import run_live_server
    run_live_server(host=host, port=port, title=title)


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


def _load_key(key_arg: str | None, key_file: str | None) -> bytes | None:
    if key_file:
        from pathlib import Path
        return Path(key_file).read_bytes().strip()
    if key_arg:
        return key_arg.encode("utf-8")
    return None


@main.command("sign")
@click.option("--algo", type=click.Choice(["crc32", "sha256", "hmac"]),
              default="sha256", help="Integrity algorithm")
@click.option("--key", default=None,
              help="HMAC key as string (required for --algo hmac)")
@click.option("--key-file", default=None, type=click.Path(exists=True),
              help="Read HMAC key from a file (preferred for secrets)")
def cmd_sign(algo: str, key: str | None, key_file: str | None) -> None:
    """Append an integrity trailer to an ADP document from stdin."""
    raw = sys.stdin.read().rstrip("\n")
    k = _load_key(key, key_file)
    if algo == "hmac" and not k:
        raise click.ClickException("hmac requires --key or --key-file")
    try:
        signed = integrity_sign(raw, algo=algo, key=k)
    except ValueError as e:
        raise click.ClickException(str(e))
    sys.stdout.write(signed)


@main.command("verify")
@click.option("--key", default=None, help="HMAC key as string")
@click.option("--key-file", default=None, type=click.Path(exists=True),
              help="Read HMAC key from a file")
@click.option("--strict/--no-strict", default=True,
              help="Fail if no integrity trailer is present (default: strict)")
@click.option("--strip-only", is_flag=True,
              help="Strip the trailer without verifying (NOT recommended)")
def cmd_verify(key: str | None, key_file: str | None,
               strict: bool, strip_only: bool) -> None:
    """Verify integrity trailer and emit the clean ADP document on stdout.

    Exit code 0 if the message is intact, 1 if tampered or missing trailer.
    """
    raw = sys.stdin.read().rstrip("\n")
    if strip_only:
        sys.stdout.write(integrity_strip(raw))
        return
    k = _load_key(key, key_file)
    try:
        clean = integrity_verify(raw, key=k, strict=strict)
    except IntegrityError as e:
        click.echo(f"INTEGRITY FAILURE: {e}", err=True)
        sys.exit(1)
    sys.stdout.write(clean)


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


@main.command("dashboard")
@click.option("--path", default=None, type=click.Path(),
              help="Path to lut_state.json (default: ~/.adp/lut_state.json)")
@click.option("--output", "-o", default=None, type=click.Path(),
              help="Write HTML to file instead of stdout")
@click.option("--title", default="ADP Dashboard", help="Page title")
def cmd_dashboard(path: str | None, output: str | None, title: str) -> None:
    """Generate a standalone HTML dashboard from session metrics."""
    from pathlib import Path as P
    from adp.session import ADPSession, DEFAULT_PATH

    lut_path = P(path) if path else DEFAULT_PATH
    if not lut_path.exists():
        raise click.ClickException(
            f"Session file not found: {lut_path}\n"
            f"Use ADPSession to generate metrics first."
        )

    session = ADPSession(path=str(lut_path), auto_save=False, announce_caps=False)
    from adp.dashboard import render_dashboard
    html = render_dashboard(session.history, title=title)

    if output:
        out_path = P(output)
        out_path.write_text(html, encoding="utf-8")
        click.echo(f"Dashboard written to {out_path}", err=True)
    else:
        sys.stdout.write(html)


if __name__ == "__main__":
    main()
