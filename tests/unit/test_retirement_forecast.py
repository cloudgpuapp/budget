import numpy as np
import pytest

from budget.retirement_forecast import (
    RetirementForecastConfig,
    block_bootstrap_paths,
    build_contribution_schedule,
    probability_of_reaching_target,
    simulate_wealth,
    summarize_terminal_wealth,
)


def test_config_calculates_month_horizons():
    config = RetirementForecastConfig(
        current_age=30, retirement_age=60, life_expectancy=85
    )

    assert config.horizon_months == 660
    assert config.accumulation_months == 360


def test_block_bootstrap_is_seeded_and_keeps_return_inflation_pairs():
    returns = np.array([0.1, 0.2, 0.3, 0.4])
    inflation = returns + 1

    sampled_returns, sampled_inflation = block_bootstrap_paths(
        returns,
        inflation,
        horizon_months=5,
        block_length=2,
        n_simulations=3,
        rng=np.random.default_rng(17),
    )
    repeated_returns, repeated_inflation = block_bootstrap_paths(
        returns,
        inflation,
        horizon_months=5,
        block_length=2,
        n_simulations=3,
        rng=np.random.default_rng(17),
    )

    assert sampled_returns.shape == (3, 5)
    np.testing.assert_array_equal(sampled_returns, repeated_returns)
    np.testing.assert_array_equal(sampled_inflation, repeated_inflation)
    np.testing.assert_array_equal(sampled_inflation, sampled_returns + 1)


def test_block_bootstrap_rejects_block_larger_than_history():
    with pytest.raises(ValueError, match="can't exceed the data length"):
        block_bootstrap_paths(
            np.ones(2), np.zeros(2), 4, 3, 1, np.random.default_rng(0)
        )


def test_fixed_contributions_stop_at_accumulation_horizon():
    schedule = build_contribution_schedule(
        "fixed", 50, 2, 4, np.zeros((2, 4))
    )

    np.testing.assert_array_equal(schedule, [[50, 50, 0, 0], [50, 50, 0, 0]])


def test_inflation_ramped_contributions_compound_inflation():
    inflation = np.array([[0.1, 0.2, 0.3]])

    schedule = build_contribution_schedule("inflation_ramp", 100, 3, 3, inflation)

    np.testing.assert_allclose(schedule, [[110, 132, 171.6]])


def test_unknown_contribution_mode_is_rejected():
    with pytest.raises(ValueError, match="Unknown contribution mode"):
        build_contribution_schedule("variable", 100, 2, 2, np.zeros((1, 2)))


def test_simulate_wealth_tracks_nominal_and_real_values():
    nominal, real = simulate_wealth(
        100,
        np.array([[0.1, 0.0]]),
        np.array([[0.0, 0.1]]),
        np.array([[10.0, 0.0]]),
    )

    np.testing.assert_allclose(nominal, [[100, 120, 120]])
    np.testing.assert_allclose(real, [[100, 120, 120 / 1.1]])


def test_summary_and_target_probability():
    summary = summarize_terminal_wealth(np.array([0.0, 10.0, 20.0]))

    assert summary.loc[50, "real_terminal_wealth"] == "$10"
    assert probability_of_reaching_target(np.array([0, 10, 20]), 10) == pytest.approx(
        2 / 3
    )
