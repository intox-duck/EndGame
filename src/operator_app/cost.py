"""Cost calculation from token usage and configured prices."""

from __future__ import annotations

from dataclasses import dataclass

from operator_app.config import Config, ModelPrice
from operator_app.types import Usage


@dataclass(frozen=True)
class CostBreakdown:
    input_cost: float
    output_cost: float
    cached_cost: float
    currency: str

    @property
    def total(self) -> float:
        return self.input_cost + self.output_cost + self.cached_cost


def cost_for_usage(usage: Usage, price: ModelPrice, currency: str = "USD") -> CostBreakdown:
    """Cost of one usage record. Prices are per million tokens."""
    return CostBreakdown(
        input_cost=usage.input_tokens / 1_000_000 * price.input,
        output_cost=usage.output_tokens / 1_000_000 * price.output,
        cached_cost=usage.cached_input_tokens / 1_000_000 * price.cached_input,
        currency=currency,
    )


class CostMeter:
    """Accumulates usage/cost across a run for a given model."""

    def __init__(self, config: Config, model: str) -> None:
        self._price = config.price_for(model)
        self._currency = config.currency
        self.usage = Usage()

    def add(self, usage: Usage) -> CostBreakdown:
        self.usage = self.usage + usage
        return self.total()

    def total(self) -> CostBreakdown:
        return cost_for_usage(self.usage, self._price, self._currency)

    def format_total(self) -> str:
        c = self.total()
        symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(self._currency, "")
        return f"{symbol}{c.total:0.4f} {self._currency}"
