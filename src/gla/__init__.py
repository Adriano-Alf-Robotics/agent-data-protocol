"""GLA — Goal Language Agents.

Token-efficient lossless serialization format for AI agent communication.

Public API:
    encode(obj)              Python obj -> GLA string
    decode(s)                GLA string -> Python obj
    to_json(s)               GLA string -> JSON string
    from_json(s)             JSON string -> GLA string
    to_markdown(s)           GLA string -> Markdown string (one-way)
    system_prompt()          Returns system prompt template for LLM
    few_shot_examples()      Returns list of (obj, gla) example pairs
    GLAParseError            Exception raised on parse failure
"""

from gla.parser import decode, GLAParseError
from gla.serializer import encode
from gla.converters import to_json, from_json, to_markdown
from gla.prompt import system_prompt, few_shot_examples

__version__ = "0.1.0"

__all__ = [
    "encode",
    "decode",
    "to_json",
    "from_json",
    "to_markdown",
    "system_prompt",
    "few_shot_examples",
    "GLAParseError",
    "__version__",
]
