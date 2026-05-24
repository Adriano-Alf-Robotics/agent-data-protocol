"""ADP — Adriano Dal Pastro format.

Token-efficient lossless serialization format for AI agent communication.
Supports nested structures, bytes, tables with nested cells, and aggressive
bare-string economy. v0.2 grammar breaks v0.1 compatibility intentionally.

Public API:
    encode(obj)              Python obj -> ADP string
    decode(s)                ADP string -> Python obj
    to_json(s)               ADP string -> JSON string
    from_json(s)             JSON string -> ADP string
    to_markdown(s)           ADP string -> Markdown string (one-way)
    system_prompt()          Returns system prompt template for LLM
    few_shot_examples()      Returns list of (obj, adp) example pairs
    ADPParseError            Exception raised on parse failure
"""

from adp.parser import decode, ADPParseError
from adp.serializer import encode
from adp.converters import to_json, from_json, to_markdown, to_html
from adp.prompt import system_prompt, few_shot_examples, few_shot_block
from adp.lut import DEFAULT_AGENT_LUT, validate_lut
from adp import tpd
from adp.db import ADPStore
from adp import integrity
from adp.integrity import sign, verify, is_signed, IntegrityError
from adp.session import ADPSession, ADPLUTSyncError  # noqa: E402
try:
    from adp import image
except ImportError:
    image = None  # type: ignore

__version__ = "0.2.0"

__all__ = [
    "encode",
    "decode",
    "to_json",
    "from_json",
    "to_markdown",
    "to_html",
    "system_prompt",
    "few_shot_examples",
    "few_shot_block",
    "ADPParseError",
    "DEFAULT_AGENT_LUT",
    "validate_lut",
    "ADPSession",
    "ADPLUTSyncError",
    "__version__",
]
