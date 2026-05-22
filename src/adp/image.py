"""ADP image compression helpers.

Cinque strategie per ridurre il costo in token delle immagini quando
viaggiano nei messaggi tra agenti AI. Sono ordinate da più conservativa
(massima fedeltà visiva) a più aggressiva (rappresentazione semantica
o riferimento esterno).

Dipendenza opzionale: Pillow (PIL). Per pHash anche imagehash.

Uso tipico:
    from adp.image import compress_for_llm, decompress
    payload = compress_for_llm(img_bytes, strategy="thumbnail_jpeg", size=64, quality=50)
    # payload è un dict pronto da passare a adp.encode()
"""

from __future__ import annotations

import base64
import io
from typing import Any, Literal

try:
    from PIL import Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    import imagehash
    _IMAGEHASH_OK = True
except ImportError:
    _IMAGEHASH_OK = False


Strategy = Literal[
    "passthrough",        # bytes inline tali e quali
    "thumbnail_jpeg",     # resize + JPEG lossy (raccomandato)
    "thumbnail_webp",     # resize + WEBP (più efficiente di JPEG)
    "perceptual_hash",    # 64-bit pHash, solo similarity
    "bitmap_8x8",         # 8x8 RGB bitmap (192 byte raw, ~200 tok)
    "caption",            # solo metadati + caption testuale
    "hybrid",             # thumb + pHash + caption (best balance)
]


def _require_pil() -> None:
    if not _PIL_OK:
        raise ImportError("Pillow non installato. uv add --optional bench pillow")


def _to_pil(img: Any) -> "Image.Image":
    if hasattr(img, "save"):           # already PIL Image
        return img
    if isinstance(img, (bytes, bytearray)):
        return Image.open(io.BytesIO(bytes(img)))
    raise TypeError(f"Non posso convertire {type(img).__name__} in immagine PIL")


def _b64(data: bytes) -> bytes:
    """Return base64-encoded bytes (so ADP encodes them via b!<base64>)."""
    return data


def passthrough(img_bytes: bytes, *, fmt: str = "PNG") -> dict[str, Any]:
    """Strategia banale: bytes inline. Massimo costo, zero perdita."""
    return {"data": img_bytes, "format": fmt}


def thumbnail_jpeg(img: Any, *, size: int = 64, quality: int = 50) -> dict[str, Any]:
    """Resize aggressivo + JPEG lossy. Buon equilibrio per analisi LLM."""
    _require_pil()
    pil = _to_pil(img).convert("RGB")
    pil.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=quality, optimize=True)
    return {
        "data": buf.getvalue(),
        "format": "JPEG",
        "w": pil.size[0],
        "h": pil.size[1],
        "quality": quality,
        "strategy": "thumbnail_jpeg",
    }


def thumbnail_webp(img: Any, *, size: int = 64, quality: int = 50) -> dict[str, Any]:
    """Resize + WEBP. Tipicamente 20-40% in meno token rispetto a JPEG."""
    _require_pil()
    pil = _to_pil(img).convert("RGB")
    pil.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    pil.save(buf, format="WEBP", quality=quality)
    return {
        "data": buf.getvalue(),
        "format": "WEBP",
        "w": pil.size[0],
        "h": pil.size[1],
        "quality": quality,
        "strategy": "thumbnail_webp",
    }


def perceptual_hash(img: Any, *, hash_size: int = 8) -> dict[str, Any]:
    """Solo similarity. 64-bit hash + opzionalmente dimensioni sorgente."""
    _require_pil()
    if not _IMAGEHASH_OK:
        raise ImportError("imagehash non installato")
    pil = _to_pil(img)
    h = imagehash.phash(pil, hash_size=hash_size)
    return {
        "phash": str(h),
        "src_w": pil.size[0],
        "src_h": pil.size[1],
        "strategy": "perceptual_hash",
    }


def bitmap_8x8(img: Any) -> dict[str, Any]:
    """Riduzione estrema: 8x8 pixel RGB (192 byte raw).

    L'agente AI vede solo macro-blocchi di colore — sufficiente per
    dominanze cromatiche, classificazioni grossolane, similarity.
    """
    _require_pil()
    pil = _to_pil(img).convert("RGB").resize((8, 8), Image.LANCZOS)
    raw = pil.tobytes()
    return {
        "rgb_8x8": raw,
        "src_w": pil.size[0],
        "src_h": pil.size[1],
        "strategy": "bitmap_8x8",
    }


def caption_only(caption: str, *, src_w: int | None = None, src_h: int | None = None,
                 src_format: str | None = None) -> dict[str, Any]:
    """Solo descrizione testuale. Richiede vision-LLM offline che genera
    il caption a monte. Costo: 20-50 token a seconda della lunghezza.
    """
    out: dict[str, Any] = {"caption": caption, "strategy": "caption"}
    if src_w is not None:
        out["src_w"] = src_w
    if src_h is not None:
        out["src_h"] = src_h
    if src_format is not None:
        out["src_format"] = src_format
    return out


def hybrid(img: Any, *, caption: str | None = None,
           thumb_size: int = 24, thumb_quality: int = 30) -> dict[str, Any]:
    """Combo: thumb molto piccolo + pHash + caption opzionale. Best balance."""
    _require_pil()
    pil = _to_pil(img).convert("RGB")
    src_w, src_h = pil.size
    thumb = pil.copy()
    thumb.thumbnail((thumb_size, thumb_size), Image.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=thumb_quality, optimize=True)
    out: dict[str, Any] = {
        "thumb": buf.getvalue(),
        "thumb_w": thumb.size[0],
        "thumb_h": thumb.size[1],
        "src_w": src_w,
        "src_h": src_h,
        "strategy": "hybrid",
    }
    if _IMAGEHASH_OK:
        out["phash"] = str(imagehash.phash(pil))
    if caption:
        out["caption"] = caption
    return out


def compress_for_llm(img: Any, *, strategy: Strategy = "thumbnail_jpeg", **kwargs) -> dict[str, Any]:
    """Wrapper unico: scelta strategia + parametri."""
    fns = {
        "passthrough":     passthrough,
        "thumbnail_jpeg":  thumbnail_jpeg,
        "thumbnail_webp":  thumbnail_webp,
        "perceptual_hash": perceptual_hash,
        "bitmap_8x8":      bitmap_8x8,
        "caption":         caption_only,
        "hybrid":          hybrid,
    }
    if strategy not in fns:
        raise ValueError(f"strategy sconosciuta: {strategy}")
    if strategy == "caption":
        return caption_only(**kwargs)
    return fns[strategy](img, **kwargs)


def decompress(payload: dict[str, Any]) -> "Image.Image | None":
    """Recupera l'immagine dal payload (se la strategia lo consente)."""
    _require_pil()
    if "data" in payload:
        return Image.open(io.BytesIO(payload["data"]))
    if "thumb" in payload:
        return Image.open(io.BytesIO(payload["thumb"]))
    if "rgb_8x8" in payload:
        raw = payload["rgb_8x8"]
        img = Image.frombytes("RGB", (8, 8), raw)
        # opzionale upscale a dimensione sorgente
        sw = payload.get("src_w", 8)
        sh = payload.get("src_h", 8)
        return img.resize((sw, sh), Image.NEAREST)
    return None  # solo metadati o solo hash


def hamming_distance(p1: dict[str, Any], p2: dict[str, Any]) -> int | None:
    """Calcola similarity tra due payload con pHash. None se mancano hash."""
    if not _IMAGEHASH_OK:
        return None
    h1 = p1.get("phash") or p1.get("hash")
    h2 = p2.get("phash") or p2.get("hash")
    if not (h1 and h2):
        return None
    return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)
