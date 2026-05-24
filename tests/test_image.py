"""Tests for adp.image compression strategies."""

from __future__ import annotations

import io
import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image

import adp
from adp.image import (
    compress_for_llm,
    decompress,
    perceptual_hash,
    hamming_distance,
)


def _make_image(size: int = 64) -> bytes:
    img = Image.new("RGB", (size, size), (200, 100, 50))
    for x in range(size):
        for y in range(size):
            img.putpixel((x, y), (x * 4 % 256, y * 4 % 256, (x + y) * 2 % 256))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_passthrough_roundtrip() -> None:
    src = _make_image()
    p = compress_for_llm(src, strategy="passthrough")
    adp_s = adp.encode({"img": p})
    back = adp.decode(adp_s)
    assert back["img"]["data"] == src


def test_thumbnail_jpeg_compresses() -> None:
    # Use a noisy 512x512 (poorly PNG-compressible) so the JPEG thumbnail wins
    img = Image.new("RGB", (512, 512), (200, 100, 50))
    for x in range(512):
        for y in range(512):
            img.putpixel((x, y), ((x * 7) & 0xFF, (y * 11) & 0xFF, ((x + y) * 13) & 0xFF))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    src = buf.getvalue()
    p = compress_for_llm(src, strategy="thumbnail_jpeg", size=64, quality=50)
    assert len(p["data"]) < len(src), "thumbnail should be smaller than source"
    assert p["w"] <= 64 and p["h"] <= 64
    out = decompress(p)
    assert out is not None and out.size[0] <= 64


def test_thumbnail_webp() -> None:
    src = _make_image(128)
    p = compress_for_llm(src, strategy="thumbnail_webp", size=64, quality=40)
    assert p["format"] == "WEBP"
    img = decompress(p)
    assert img is not None


def test_perceptual_hash_similarity() -> None:
    src1 = _make_image(128)
    img2 = Image.open(io.BytesIO(src1)).convert("RGB")
    # Apply tiny perturbation
    for _ in range(50):
        x = 17 % 128
        y = 23 % 128
        img2.putpixel((x, y), (0, 0, 0))
    buf = io.BytesIO()
    img2.save(buf, format="PNG")
    src2 = buf.getvalue()

    p1 = perceptual_hash(src1)
    p2 = perceptual_hash(src2)
    d = hamming_distance(p1, p2)
    assert d is not None
    assert d <= 4, f"similar images should have small hamming distance, got {d}"


def test_bitmap_8x8_roundtrip_lossy() -> None:
    src = _make_image(64)
    p = compress_for_llm(src, strategy="bitmap_8x8")
    assert len(p["rgb_8x8"]) == 192     # 8 * 8 * 3
    img = decompress(p)
    # decompress upscales to src dims as recorded in payload
    assert img.size == (p["src_w"], p["src_h"])


def test_caption_only() -> None:
    p = compress_for_llm(None, strategy="caption",
                         caption="a red triangle on white background",
                         src_w=512, src_h=512, src_format="PNG")
    assert "caption" in p
    assert decompress(p) is None        # no image bytes to recover


def test_hybrid_contains_thumb_and_hash() -> None:
    src = _make_image(128)
    p = compress_for_llm(src, strategy="hybrid",
                         caption="test", thumb_size=24, thumb_quality=30)
    assert "thumb" in p
    assert "phash" in p
    assert p["caption"] == "test"


def test_image_module_attribute_error_helpful_if_missing():
    """Se Pillow è installato (caso comune in dev), test skip; se assente,
    accesso a adp.image.compress_for_llm deve sollevare ImportError chiaro."""
    import adp
    try:
        import PIL  # noqa: F401
        # Pillow presente: il test non si applica
        return
    except ImportError:
        pass
    # Pillow assente: verifica messaggio chiaro
    with pytest.raises(ImportError, match="pip install adp"):
        _ = adp.image.compress_for_llm  # type: ignore


def test_adp_encode_decode_with_image_payload() -> None:
    src = _make_image(128)
    p = compress_for_llm(src, strategy="hybrid", caption="x")
    full = {"task": "describe", "image": p}
    s = adp.encode(full)
    back = adp.decode(s)
    assert back["image"]["caption"] == "x"
    assert back["image"]["thumb"] == p["thumb"]   # bytes preserved
