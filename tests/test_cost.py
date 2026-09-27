from __future__ import annotations

import pytest

from operator_app.config import Config, ConfigError, ModelPrice
from operator_app.cost import CostMeter, cost_for_usage
from operator_app.types import Usage


def test_cost_for_usage():
    price = ModelPrice(input=1.50, output=9.00, cached_input=0.15)
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000,
                  cached_input_tokens=1_000_000)
    c = cost_for_usage(usage, price)
    assert c.input_cost == pytest.approx(1.50)
    assert c.output_cost == pytest.approx(9.00)
    assert c.cached_cost == pytest.approx(0.15)
    assert c.total == pytest.approx(10.65)


def test_cost_meter_accumulates():
    cfg = Config()
    meter = CostMeter(cfg, "gemini-3.5-flash")
    meter.add(Usage(input_tokens=1000, output_tokens=200))
    meter.add(Usage(input_tokens=1000, output_tokens=200))
    assert meter.usage.input_tokens == 2000
    assert meter.total().total > 0


def test_meter_unknown_model_raises():
    cfg = Config(prices={})
    with pytest.raises(ConfigError):
        CostMeter(cfg, "no-such-model")


def test_format_total_currency_symbol():
    cfg = Config(currency="GBP")
    meter = CostMeter(cfg, "gemini-3.5-flash")
    meter.add(Usage(input_tokens=1_000_000))
    assert meter.format_total().startswith("£")
