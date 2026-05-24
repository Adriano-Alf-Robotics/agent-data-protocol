"""Pricing per provider LLM, in $ per milione di token (input).

Numeri aggiornati a maggio 2026. Usati per stimare il costo $ delle
conversazioni nei benchmark.
"""
from __future__ import annotations

# $ per 1M input tokens (i token che paghi quando emetti messaggi al modello)
PRICING_INPUT_PER_MTOK: dict[str, float] = {
    # Anthropic Claude 4.x family
    "claude-opus-4-7": 15.00,
    "claude-sonnet-4-6": 3.00,
    "claude-haiku-4-5": 0.80,
    # OpenAI
    "gpt-4o": 2.50,
    "gpt-4o-mini": 0.15,
    "o1": 15.00,
    "o3-mini": 1.10,
}


def cost_estimate(tokens: int, model: str = "claude-sonnet-4-6") -> float:
    """Stima il costo $ per `tokens` input al modello indicato.

    Ritorna 0.0 se model non riconosciuto (con warning silenzioso).
    """
    rate = PRICING_INPUT_PER_MTOK.get(model, 0.0)
    return tokens * rate / 1_000_000


def format_cost(cost: float) -> str:
    """Formatta $ in modo leggibile (4 cifre dopo decimal se < 1$)."""
    if cost < 0.0001:
        return f"${cost*1000:.4f}m"  # millesimi
    if cost < 1.0:
        return f"${cost:.4f}"
    return f"${cost:.2f}"
