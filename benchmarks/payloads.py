"""Canonical benchmark payloads.

Six categories, each available in EN and IT variants where text content matters.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# 1. Plain short string (typical agent reply)
# ---------------------------------------------------------------------------
SHORT_STRING_EN: dict[str, Any] = {
    "intent": "ack",
    "msg": "Task received. Working on it.",
}

SHORT_STRING_IT: dict[str, Any] = {
    "intent": "ack",
    "msg": "Compito ricevuto. Sto lavorando.",
}


# ---------------------------------------------------------------------------
# 2. Long text / multi-paragraph
# ---------------------------------------------------------------------------
LONG_TEXT_EN: dict[str, Any] = {
    "title": "Quarterly Summary",
    "body": (
        "Revenue grew 12% year over year, driven primarily by enterprise sales in "
        "the EMEA region. Operational expenses remained flat, expanding margins.\n\n"
        "Customer churn dropped to 2.1%, the lowest in six quarters. Net-new logos "
        "added: 47. Top-three industries by ARR: SaaS, Fintech, Healthcare.\n\n"
        "Outlook: cautious optimism. Macro headwinds persist but pipeline coverage "
        "for the next quarter stands at 3.4x, above the 3.0x threshold."
    ),
}

LONG_TEXT_IT: dict[str, Any] = {
    "titolo": "Sintesi Trimestrale",
    "corpo": (
        "Il fatturato è cresciuto del 12% anno su anno, trainato principalmente "
        "dalle vendite enterprise in area EMEA. I costi operativi sono rimasti "
        "stabili, ampliando i margini.\n\n"
        "L'abbandono clienti è sceso al 2,1%, il valore più basso degli ultimi "
        "sei trimestri. Nuovi clienti acquisiti: 47. Top tre settori per ARR: "
        "SaaS, Fintech, Sanità.\n\n"
        "Prospettive: ottimismo cauto. Le difficoltà macroeconomiche persistono "
        "ma la copertura di pipeline per il prossimo trimestre è pari a 3,4x, "
        "sopra la soglia di 3,0x."
    ),
}


# ---------------------------------------------------------------------------
# 3. Special characters (escape stress test)
# ---------------------------------------------------------------------------
SPECIAL_CHARS_EN: dict[str, Any] = {
    "code_snippet": 'function f(x) {\n  return x["a\\b\\"c"] + 1;\n}',
    "emoji": "Done ✅ 🎉 — 100% reliable 🚀",
    "math": "α + β = γ; ∑ᵢ xᵢ → ∞",
    "quoted_quotes": 'She said "hi" and left.',
    "backslash_path": "C:\\Users\\admin\\file.txt",
}

SPECIAL_CHARS_IT: dict[str, Any] = {
    "frammento_codice": 'function f(x) {\n  return x["a\\b\\"c"] + 1;\n}',
    "emoji": "Fatto ✅ 🎉 — affidabile al 100% 🚀",
    "matematica": "α + β = γ; ∑ᵢ xᵢ → ∞",
    "virgolette": 'Ha detto "ciao" e se n\'è andata.',
    "percorso": "C:\\Utenti\\admin\\file.txt",
    "accenti": "città, perché, già, può, è, à, ò, ù, ì",
}


# ---------------------------------------------------------------------------
# 4. CSV-like tabular dataset
# ---------------------------------------------------------------------------
def _employees(language: str = "en") -> dict[str, Any]:
    if language == "it":
        return {
            "dipendenti": [
                {"id": 1, "nome": "Alice", "dipartimento": "Vendite", "stipendio": 52000.0, "attivo": True},
                {"id": 2, "nome": "Bruno", "dipartimento": "Tecnico", "stipendio": 68000.0, "attivo": True},
                {"id": 3, "nome": "Carla", "dipartimento": "Vendite", "stipendio": 55000.0, "attivo": False},
                {"id": 4, "nome": "Davide", "dipartimento": "Tecnico", "stipendio": 72000.0, "attivo": True},
                {"id": 5, "nome": "Elena", "dipartimento": "Marketing", "stipendio": 49000.0, "attivo": True},
                {"id": 6, "nome": "Fabio", "dipartimento": "Tecnico", "stipendio": 80000.0, "attivo": True},
                {"id": 7, "nome": "Giulia", "dipartimento": "Vendite", "stipendio": 53000.0, "attivo": True},
                {"id": 8, "nome": "Hugo", "dipartimento": "Marketing", "stipendio": 51000.0, "attivo": False},
                {"id": 9, "nome": "Irene", "dipartimento": "Tecnico", "stipendio": 75000.0, "attivo": True},
                {"id": 10, "nome": "Luca", "dipartimento": "Vendite", "stipendio": 56000.0, "attivo": True},
            ]
        }
    return {
        "employees": [
            {"id": 1, "name": "Alice", "department": "Sales", "salary": 52000.0, "active": True},
            {"id": 2, "name": "Bruno", "department": "Engineering", "salary": 68000.0, "active": True},
            {"id": 3, "name": "Carla", "department": "Sales", "salary": 55000.0, "active": False},
            {"id": 4, "name": "David", "department": "Engineering", "salary": 72000.0, "active": True},
            {"id": 5, "name": "Elena", "department": "Marketing", "salary": 49000.0, "active": True},
            {"id": 6, "name": "Fabio", "department": "Engineering", "salary": 80000.0, "active": True},
            {"id": 7, "name": "Grace", "department": "Sales", "salary": 53000.0, "active": True},
            {"id": 8, "name": "Hugo", "department": "Marketing", "salary": 51000.0, "active": False},
            {"id": 9, "name": "Irene", "department": "Engineering", "salary": 75000.0, "active": True},
            {"id": 10, "name": "Luca", "department": "Sales", "salary": 56000.0, "active": True},
        ]
    }


TABULAR_EN = _employees("en")
TABULAR_IT = _employees("it")


# ---------------------------------------------------------------------------
# 5. Database-like nested record
# ---------------------------------------------------------------------------
DATABASE_EN: dict[str, Any] = {
    "order": {
        "id": "ORD-2026-04018",
        "customer": {
            "id": 7412,
            "name": "Acme Corp.",
            "email": "ops@acme.example",
            "vip": True,
        },
        "items": [
            {"sku": "A1", "qty": 2, "unit_price": 19.99},
            {"sku": "B7", "qty": 1, "unit_price": 149.0},
            {"sku": "C3", "qty": 5, "unit_price": 4.5},
        ],
        "shipping": {
            "address": "12 Market St, Springfield, IL 62701, USA",
            "method": "standard",
            "tracking": None,
        },
        "totals": {"subtotal": 212.48, "tax": 17.0, "total": 229.48},
        "paid": True,
        "notes": "Leave at the back door if no answer.",
    }
}


DATABASE_IT: dict[str, Any] = {
    "ordine": {
        "id": "ORD-2026-04018",
        "cliente": {
            "id": 7412,
            "ragione_sociale": "Acme S.r.l.",
            "email": "ops@acme.example",
            "vip": True,
        },
        "articoli": [
            {"sku": "A1", "qta": 2, "prezzo_unitario": 19.99},
            {"sku": "B7", "qta": 1, "prezzo_unitario": 149.0},
            {"sku": "C3", "qta": 5, "prezzo_unitario": 4.5},
        ],
        "spedizione": {
            "indirizzo": "Via Roma 12, 35100 Padova, Italia",
            "metodo": "standard",
            "tracking": None,
        },
        "totali": {"imponibile": 212.48, "iva": 46.74, "totale": 259.22},
        "pagato": True,
        "note": "Lasciare sulla porta sul retro in caso di assenza.",
    }
}


# ---------------------------------------------------------------------------
# 6. Multi-agent task envelope (typical inter-agent payload)
# ---------------------------------------------------------------------------
AGENT_TASK_EN: dict[str, Any] = {
    "msg_id": "m_8c14",
    "from_agent": "planner",
    "to_agent": "executor",
    "intent": "execute_step",
    "step": {
        "n": 3,
        "tool": "shell",
        "command": "uv run pytest -k 'roundtrip'",
        "timeout_s": 60,
    },
    "context": {
        "task_id": "T-204",
        "previous_outputs": ["compile ok", "lint ok"],
        "constraints": ["must_pass_tests", "no_external_network"],
    },
    "expected_reply": "step_result",
}

AGENT_TASK_IT: dict[str, Any] = {
    "msg_id": "m_8c14",
    "agente_da": "pianificatore",
    "agente_a": "esecutore",
    "intento": "esegui_passo",
    "passo": {
        "n": 3,
        "strumento": "shell",
        "comando": "uv run pytest -k 'roundtrip'",
        "timeout_s": 60,
    },
    "contesto": {
        "task_id": "T-204",
        "output_precedenti": ["compilazione ok", "lint ok"],
        "vincoli": ["test_devono_passare", "rete_esterna_vietata"],
    },
    "risposta_attesa": "risultato_passo",
}


PAYLOADS: dict[str, dict[str, Any]] = {
    "short_string_en": SHORT_STRING_EN,
    "short_string_it": SHORT_STRING_IT,
    "long_text_en": LONG_TEXT_EN,
    "long_text_it": LONG_TEXT_IT,
    "special_chars_en": SPECIAL_CHARS_EN,
    "special_chars_it": SPECIAL_CHARS_IT,
    "tabular_en": TABULAR_EN,
    "tabular_it": TABULAR_IT,
    "database_en": DATABASE_EN,
    "database_it": DATABASE_IT,
    "agent_task_en": AGENT_TASK_EN,
    "agent_task_it": AGENT_TASK_IT,
}
