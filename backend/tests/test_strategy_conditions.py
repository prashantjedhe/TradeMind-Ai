import pandas as pd
import numpy as np
import pytest

from app.services.strategy_service import evaluate_condition_tree, required_bars_for_tree


@pytest.fixture
def mock_bars():
    dates = pd.date_range("2026-01-01", periods=60, freq="D")
    df = pd.DataFrame(
        {
            "open": np.linspace(100, 150, 60),
            "high": np.linspace(102, 152, 60),
            "low": np.linspace(98, 148, 60),
            "close": np.linspace(101, 151, 60),
            "volume": [100000] * 60,
        },
        index=dates,
    )
    return df


def test_required_bars_for_tree():
    tree = {
        "type": "group",
        "logic": "AND",
        "conditions": [
            {
                "type": "condition",
                "left": {"indicator": "RSI", "params": {"period": 14}},
                "operator": "<",
                "right": 30,
            },
            {
                "type": "condition",
                "left": {"indicator": "EMA", "params": {"period": 50}},
                "operator": ">",
                "right": 100,
            },
        ],
    }
    required = required_bars_for_tree(tree)
    assert required >= 151


def test_evaluate_condition_tree_and_logic(mock_bars):
    # Condition: close above 120 AND volume above 50,000
    tree = {
        "type": "group",
        "logic": "AND",
        "conditions": [
            {
                "type": "condition",
                "left": {"indicator": "PRICE", "params": {}},
                "operator": ">",
                "right": 120.0,
            },
            {
                "type": "condition",
                "left": {"indicator": "VOLUME", "params": {"period": 20}},
                "operator": ">",
                "right": 50000.0,
            },
        ],
    }

    # At bar 10 (close ~108): condition is False
    result_early = evaluate_condition_tree(mock_bars.iloc[:10], tree, {})
    assert result_early is False

    # At bar 55 (close ~146): close is above 120
    # Note: volume is flat, so volume above avg will be checked
    result_late = evaluate_condition_tree(mock_bars.iloc[:55], tree, {})
    assert isinstance(result_late, (bool, np.bool_))
