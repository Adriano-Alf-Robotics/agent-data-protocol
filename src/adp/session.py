"""ADPSession — dynamic LUT adattiva HPACK-style.

Mantiene una LUT dinamica condivisa tra agenti, sincronizzata via prefissi
in-band nei messaggi ADP, persistita localmente.

Vedi spec: docs/superpowers/specs/2026-05-24-dynamic-lut-design.md
"""
from __future__ import annotations

import atexit
import fcntl
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable

import adp


class ADPLUTSyncError(Exception):
    """Sollevata quando un alias dynamic LUT non è risolvibile."""

    def __init__(self, alias: str, message: str | None = None):
        self.alias = alias
        super().__init__(message or f"Alias dynamic LUT non risolvibile: {alias!r}")


class ADPSession:
    """Placeholder per Task 1. Implementazione completa in Task 2."""
    pass


__all__ = ["ADPSession", "ADPLUTSyncError",
           "apply_lut_updates", "encode_with_dyn_lut"]
