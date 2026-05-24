# ADP Image Handling

> Purpose: strategies for sending images between agents efficiently — from full-quality passthrough to perceptual hashing, plus the ADP-DB approach for recurring assets.
> Back to [main README](../README.md)

---

## Overview

Raster images are a special case. Once converted to base64 for the text
channel, their token cost is dominated by the base64 itself, not by the
wrapper syntax. Measurement on a synthetic 128×128 RGBA PNG:

| Format | Token cl100k | Notes |
|---|---:|---|
| JSON with `"data_b64":"..."` | 54,462 | base64 + JSON syntax |
| ADP with `data=b!...` | 54,457 | base64 + ADP syntax |
| RAW pure base64 | 54,425 | no wrapper, no metadata |

The difference between the three is less than 0.1%. On inline binaries the
wrapper does not matter — base64 dominates the cost.

ADP addresses the problem in two complementary directions: treating images as
**references** (ADP-DB) or compressing them with **lossy strategies** targeted
at LLM consumption (the `adp.image` module).

---

## Lossy inline strategies (`adp.image` module)

Measurements on a source PNG 256×256 RGB (gradient + shapes), baseline 2,842
cl100k tokens for the lossless version:

| Strategy | Tokens | Δ vs PNG | Lossless | Ideal case |
|---|---:|---:|:---:|---|
| `passthrough` (PNG inline) | 2,842 | — | ✓ | maximum quality required |
| `thumbnail_webp` q30 256×256 | 1,438 | **−49%** | ✗ | full-resolution lossy |
| `thumbnail_jpeg` size=128 q20 | 1,353 | **−52%** | ✗ | decent quality |
| `thumbnail_jpeg` size=64 q50 | 934 | **−67%** | ✗ | generic LLM analysis |
| `thumbnail_jpeg` size=32 q30 | 524 | **−82%** | ✗ | visual essence |
| `hybrid` (thumb 24×24 + pHash + caption) | 550 | **−81%** | ✗ | best balance |
| `bitmap_8x8` (8×8 RGB raw) | 182 | **−94%** | ✗ | dominant colors |
| `caption` (text description) | 27 | **−99%** | ✗ | offline vision available |
| `perceptual_hash` (64-bit) | 11 | **−99.6%** | ✗ | similarity check only |
| ADP-DB ref `^id` (after bootstrap) | 5 | **−99.8%** | ✓ | recurring asset |

---

## API

```python
import adp
from adp.image import compress_for_llm, decompress, hamming_distance

# Strategia raccomandata generale: thumbnail 64×64 JPEG q50
payload = compress_for_llm(img_bytes, strategy="thumbnail_jpeg", size=64, quality=50)
msg = adp.encode({"task": "describe", "image": payload})
# ~930 token vs ~2840 PNG inline

# Hybrid: thumbnail visibile + hash + caption + metadati
payload = compress_for_llm(img_bytes, strategy="hybrid",
                            thumb_size=24, thumb_quality=30,
                            caption="red square on blue gradient")
# ~550 token, contiene tutto ciò che serve per analisi + similarity

# Perceptual hash: solo similarity check, nessuna decompressione
p1 = compress_for_llm(img_a, strategy="perceptual_hash")
p2 = compress_for_llm(img_b, strategy="perceptual_hash")
distance = hamming_distance(p1, p2)   # 0 = identici, basso = simili
```

Seven strategies available: `passthrough`, `thumbnail_jpeg`,
`thumbnail_webp`, `perceptual_hash`, `bitmap_8x8`, `caption`,
`hybrid`. All produce dicts compatible with `adp.encode()`.

---

## ADP-DB strategy for recurring assets

When the same assets (avatars, icons, reference screenshots) travel multiple
times between the same agents, ADP-DB promotes them to short identifiers in the
shared database. Bootstrap cost is paid once; follow-up references are
essentially free.

```python
from adp import ADPStore

store = ADPStore(path="agents_shared.json")
with open("avatar_42.png", "rb") as f:
    img_id = store.put(f.read().decode("latin1"))
store.save()

# Messaggi successivi: ~5 token al posto di ~14.000
msg = adp.encode({"task": "lookup_user", "avatar_ref": img_id})
```

On a workload of one hundred calls reusing three images, the total measured
savings are approximately **16 million tokens** compared to repeated inline
sending.

---

## Quick decision tree

| Need | Recommended strategy |
|---|---|
| Identify specific objects at high resolution | `passthrough` or `thumbnail_jpeg` size=256 |
| LLM must describe or classify the image | `thumbnail_jpeg` size=64, quality=50 |
| Similarity check only between two images | `perceptual_hash` |
| Recurring assets (icons, avatars, fixed screenshots) | `ADPStore` + `^id` references |
| Offline vision-LLM available for captions | `caption` strategy |
| Best general balance (analysis + similarity) | `hybrid` |

Optional dependencies: `pillow` for resize/JPEG/WEBP, `imagehash`
for pHash. Install with `uv sync --extra bench`.
