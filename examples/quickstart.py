"""Esempio minimo di utilizzo di GLA.

Esegui con:
    uv run python examples/quickstart.py
"""

import gla


def main() -> None:
    payload = {
        "user": {"id": 42, "name": "Adriano", "active": True},
        "metrics": [
            {"id": 1, "value": 42.0, "unit": "kg"},
            {"id": 2, "value": 3.14, "unit": "m"},
        ],
        "report": 'Riga 1\nRiga 2 con "virgolette" e \\backslash\nRiga 3',
        "tags": ["admin", "root", "user con spazio"],
        "owner": None,
    }

    print("=== Encoding ===")
    encoded = gla.encode(payload)
    print(encoded)
    print()

    print("=== Round-trip (decode) ===")
    decoded = gla.decode(encoded)
    print(decoded)
    assert decoded == payload, "round-trip failed"
    print("OK: decode(encode(payload)) == payload")
    print()

    print("=== Conversione a JSON (per macchine non-AI) ===")
    print(gla.to_json(encoded))
    print()

    print("=== Conversione a Markdown (per umani) ===")
    print(gla.to_markdown(encoded))
    print()

    print("=== Persistenza ===")
    from pathlib import Path
    p = Path("/tmp/gla_demo.gla")
    p.write_text(encoded, encoding="utf-8")
    restored = gla.decode(p.read_text(encoding="utf-8"))
    assert restored == payload
    print(f"Salvato in {p} e ricaricato senza perdita di dati.")


if __name__ == "__main__":
    main()
