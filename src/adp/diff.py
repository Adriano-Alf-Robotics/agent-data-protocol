"""Differential encoding per ADPSession.

Calcola e applica diff strutturali tra due payload dict/list/scalar.
Operazioni supportate v1: set (sostituzione/aggiunta), del (rimozione).
Liste trattate come scalari atomici (qualsiasi modifica → sostituzione full
della lista via set).

Path notation per del: dot-separated, es. "user.id", "metadata.tmp".
Le liste non sono indicizzate per path (limitazione v1).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def compute_diff(base: Any, current: Any) -> dict:
    """Calcola diff strutturale tra base e current.

    Ritorna dict con chiavi opzionali 'set' e 'del':
    - 'set': nested dict sparso che mirrora le sotto-strutture modificate
    - 'del': lista di dot-paths string da rimuovere da base

    Se base == current: ritorna {}.
    Liste: comparate per uguaglianza; se diverse → full replacement via set.
    """
    set_part: dict = {}
    del_part: list[str] = []
    _diff_recursive(base, current, "", set_part, del_part)
    out: dict = {}
    if set_part:
        out["set"] = set_part
    if del_part:
        out["del"] = del_part
    return out


def _diff_recursive(base: Any, current: Any, path: str,
                    set_part: dict, del_part: list[str]) -> None:
    """Visita ricorsiva. set_part e del_part vengono mutati in-place."""
    if isinstance(base, dict) and isinstance(current, dict):
        all_keys = sorted(set(base.keys()) | set(current.keys()))
        for k in all_keys:
            child_path = f"{path}.{k}" if path else str(k)
            if k not in current:
                del_part.append(child_path)
            elif k not in base:
                _place_in_set(set_part, child_path, current[k])
            else:
                if isinstance(base[k], dict) and isinstance(current[k], dict):
                    _diff_recursive(base[k], current[k], child_path,
                                    set_part, del_part)
                elif base[k] != current[k]:
                    _place_in_set(set_part, child_path, current[k])
        return
    if base != current:
        if path == "":
            raise ValueError("compute_diff supporta solo dict al top-level")
        _place_in_set(set_part, path, current)


def _place_in_set(set_part: dict, dot_path: str, value: Any) -> None:
    """Inserisce value nella struttura set_part secondo dot_path."""
    parts = dot_path.split(".")
    cur = set_part
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def apply_diff(base: Any, diff: dict) -> Any:
    """Applica diff a base, ritorna nuovo payload (base non modificato).

    Ordine: prima delete, poi set (deep-merge). Risultato: nuovo dict.
    """
    new = deepcopy(base)
    for path in diff.get("del", []):
        _delete_at_path(new, path.split("."))
    set_part = diff.get("set", {})
    _deep_merge(new, set_part)
    return new


def _delete_at_path(obj: Any, parts: list[str]) -> None:
    """Naviga obj seguendo parts e cancella l'ultima chiave.
    No-op se path non esiste (idempotente)."""
    cur = obj
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return
        cur = cur[p]
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def _deep_merge(dst: dict, src: dict) -> None:
    """Merge ricorsivo di src in dst. dst modificato in-place."""
    for k, v in src.items():
        if (isinstance(v, dict) and isinstance(dst.get(k), dict)):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
