"""ADP — Agent Data Protocol.

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
from adp.session import ADPSession, ADPLUTSyncError, ADPDiffSyncError
from adp.lut import apply_lut_updates, encode_with_dyn_lut  # noqa: E402
from adp.cost import TokenizerCostEstimator, estimate_cost
try:
    from adp import image  # noqa: F401
except ImportError as _img_err:
    class _ImageStub:
        """Stub helpful per quando Pillow non è installato."""
        _err = str(_img_err)
        def __getattr__(self, name):
            raise ImportError(
                f"adp.image richiede dipendenze opzionali. "
                f"Installa con: pip install adp[bench]  "
                f"(missing: {self._err})"
            )
    image = _ImageStub()

__version__ = "0.3.5"

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
    "ADPDiffSyncError",
    "apply_lut_updates",
    "encode_with_dyn_lut",
    "TokenizerCostEstimator",
    "estimate_cost",
    "__version__",
]
