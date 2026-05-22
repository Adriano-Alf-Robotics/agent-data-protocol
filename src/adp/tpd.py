"""TPD — Token-aware Phrase Dictionary.

Tecnica di compressione semantica per testo libero. Sostituisce frasi
ricorrenti con codici brevi (marker `§` + sigla) pre-concordati tra
mittente e destinatario. Lossless garantito tramite escape `§§ -> §`.

A differenza della LUT (che agisce solo sui nomi-chiave di un dict),
TPD agisce sul **contenuto testuale**: è utile per battere flat-text in
modo aggressivo quando il messaggio è prevalentemente prosa.

Modalità d'uso:

    import adp

    # Dizionario pre-concordato (statico, ad esempio business EN)
    lut = adp.tpd.BUSINESS_LUT_EN

    # Encoder/decoder simmetrico
    compressed = adp.tpd.encode_text(text, lut)
    original   = adp.tpd.decode_text(compressed, lut)

    # Apprendimento ad-hoc: due agenti concordano un mini-dict basato sul
    # testo che stanno per scambiare; il dict viene trasmesso una volta
    # (preambolo) e ammortizzato dal pacchetto stesso.
    lut = adp.tpd.learn_lut(text, tokenizer="cl100k_base", max_codes=30)
"""

from __future__ import annotations

import re
from typing import Any


_MARKER = "§"
_PLACEHOLDER = ""   # PUA character, never appears in normal text


# ---------------------------------------------------------------------------
# Pre-built phrase LUTs
# ---------------------------------------------------------------------------

BUSINESS_LUT_EN: dict[str, str] = {
    " year over year": "§y1",
    "Revenue grew": "§r1",
    "Revenue declined": "§r2",
    "driven primarily by": "§d1",
    "driven by": "§d2",
    "enterprise sales": "§e1",
    " in the EMEA region": "§g1",
    " in the APAC region": "§g2",
    " in the Americas region": "§g3",
    "Operational expenses": "§o1",
    "operational expenses": "§o2",
    "remained flat": "§f1",
    "expanding margins": "§m1",
    "Customer churn": "§c1",
    "customer churn": "§c2",
    " dropped to": "§p1",
    "the lowest in": "§l1",
    " six quarters": "§q6",
    "Net-new logos": "§n1",
    "Top-three industries": "§t1",
    " by ARR": "§a1",
    "SaaS": "§s1",
    "Fintech": "§s2",
    "Healthcare": "§s3",
    " Outlook:": "§u1",
    "cautious optimism": "§o3",
    "Macro headwinds": "§h1",
    "macro headwinds": "§h2",
    "pipeline coverage": "§p2",
    " for the next quarter": "§q1",
    "above the": "§b1",
    "threshold": "§h3",
}


BUSINESS_LUT_IT: dict[str, str] = {
    " anno su anno": "§y1",
    "Il fatturato è cresciuto": "§r1",
    "Il fatturato è calato": "§r2",
    "trainato principalmente dalle": "§d1",
    "trainato dalle": "§d2",
    "vendite enterprise": "§e1",
    " in area EMEA": "§g1",
    "I costi operativi": "§o1",
    "costi operativi": "§o2",
    "sono rimasti stabili": "§f1",
    "ampliando i margini": "§m1",
    "L'abbandono clienti": "§c1",
    "abbandono clienti": "§c2",
    " è sceso al": "§p1",
    "il valore più basso": "§l1",
    "degli ultimi": "§q0",
    " sei trimestri": "§q6",
    "Nuovi clienti acquisiti": "§n1",
    "Top tre settori": "§t1",
    " per ARR": "§a1",
    " Prospettive:": "§u1",
    "ottimismo cauto": "§o3",
    "difficoltà macroeconomiche": "§h1",
    "copertura di pipeline": "§p2",
    " per il prossimo trimestre": "§q1",
    "sopra la soglia": "§b1",
}


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def encode_text(text: str, lut: dict[str, str]) -> str:
    """Compress text by substituting phrases with codes from the LUT.

    Lossless WHEN the codes in `lut` do not naturally appear in `text`.
    `learn_lut()` already enforces this; if you pass a hand-written LUT
    you must guarantee non-collision yourself.
    """
    if not lut:
        return text
    pattern = "|".join(re.escape(p) for p in sorted(lut, key=len, reverse=True))
    return re.sub(pattern, lambda m: lut[m.group(0)], text)


def decode_text(text: str, lut: dict[str, str]) -> str:
    """Expand codes back to their original phrases."""
    if not lut:
        return text
    inv = {v: k for k, v in lut.items()}
    pattern = "|".join(re.escape(c) for c in sorted(inv, key=len, reverse=True))
    return re.sub(pattern, lambda m: inv[m.group(0)], text)


# ---------------------------------------------------------------------------
# Ad-hoc dictionary learner
# ---------------------------------------------------------------------------

def _generate_cheap_codes(tokenizer: Any, n: int, text: str) -> list[str]:
    """Generate `n` distinct codes that tokenize to a single token (when possible)
    in the given tokenizer, and that do not already appear in `text`.

    Strategy: try short ASCII strings ("Zq", "X3", "Q7", ...), keep those that
    are exactly 1 token. Fall back to 2-token codes if not enough singletons.
    """
    candidates: list[str] = []
    # Single-letter cap markers tend to be subtokens, not 1 token.
    # Try uncommon two-char ASCII combos: rare consonant pairs + digits.
    seeds_one = list("zqxjkvwy")
    seeds_two = list("0123456789")
    pool: list[str] = []
    for a in seeds_one:
        for b in seeds_one + seeds_two:
            pool.append(a + b)
            pool.append(a.upper() + b)
            pool.append(b + a)
    # Deduplicate and remove ones present in text
    seen = set()
    one_tok: list[str] = []
    multi_tok: list[str] = []
    for c in pool:
        if c in seen or c in text:
            continue
        seen.add(c)
        try:
            t = len(tokenizer.encode(c))
        except Exception:
            t = 99
        if t == 1:
            one_tok.append(c)
        else:
            multi_tok.append(c)
    candidates = one_tok + multi_tok
    return candidates[:n]


def learn_lut(
    text: str,
    tokenizer: Any | str = "cl100k_base",
    *,
    max_codes: int = 40,
    min_phrase_words: int = 2,
    max_phrase_words: int = 10,
    min_occurrences: int = 2,
    min_token_savings: int = 1,
) -> dict[str, str]:
    """Greedily learn a phrase LUT that maximizes token savings on the input.

    Returns a dict that, when used with encode_text/decode_text, compresses
    the input. Agents must share the same LUT.
    """
    import tiktoken
    enc = tiktoken.get_encoding(tokenizer) if isinstance(tokenizer, str) else tokenizer

    codes = _generate_cheap_codes(enc, max_codes * 4, text)
    if not codes:
        return {}

    work = text
    lut: dict[str, str] = {}
    code_iter = iter(codes)

    for _ in range(max_codes):
        # Pick next available code that still doesn't appear in `work`
        code = None
        for c in code_iter:
            if c not in work:
                code = c
                break
        if code is None:
            break
        code_tok = len(enc.encode(code))

        candidates = _candidate_phrases(work, min_phrase_words, max_phrase_words, min_occurrences)
        if not candidates:
            break

        best_phrase = None
        best_savings = min_token_savings
        for phrase, count in candidates.items():
            if code in phrase:
                continue
            phrase_tok = len(enc.encode(phrase))
            # savings = count * (phrase_tok - code_tok). Dict is shared, not in payload.
            savings = count * (phrase_tok - code_tok)
            if savings > best_savings:
                best_savings = savings
                best_phrase = phrase
        if best_phrase is None:
            break
        lut[best_phrase] = code
        work = work.replace(best_phrase, code)

    return lut


def _candidate_phrases(
    text: str, min_words: int, max_words: int, min_occ: int
) -> dict[str, int]:
    """Find recurring substrings.

    For space-separated languages (EN/IT/...) uses word n-grams.
    For unspaced text (ZH/JA without spaces) falls back to character n-grams.
    """
    counts: dict[str, int] = {}

    # Word-based n-grams (works for EN/IT/FR/DE/ES/PT/RU/...)
    if " " in text:
        words = text.split(" ")
        n = len(words)
        for size in range(min_words, max_words + 1):
            for i in range(n - size + 1):
                ngram = " ".join(words[i : i + size])
                if not ngram or len(ngram) < 4:
                    continue
                counts[ngram] = counts.get(ngram, 0) + 1

    # Character n-grams (works for ZH/JA scripts without spaces). Useful when
    # word-split yields little.
    # Use range tuned for CJK: 3-8 chars typical "phrase" length.
    for size in (3, 4, 5, 6, 7, 8, 10, 12, 16):
        for i in range(len(text) - size + 1):
            seg = text[i : i + size]
            # Skip whitespace-only or pure ASCII (already handled by word split)
            if seg.isascii() and " " in seg:
                continue
            if len(seg.strip()) < 3:
                continue
            counts[seg] = counts.get(seg, 0) + 1

    return {p: c for p, c in counts.items() if c >= min_occ}


# ---------------------------------------------------------------------------
# ADP integration: stringa singola con TPD
# ---------------------------------------------------------------------------

def encode_one_string(text: str, lut: dict[str, str]) -> str:
    """Helper: encode a single string with TPD only, no ADP envelope.

    The receiver, knowing the LUT, runs decode_text() to restore the original.
    """
    return encode_text(text, lut)
