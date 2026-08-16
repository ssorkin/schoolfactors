"""Stage-1 recency weighting and stage-3 confidence bounds."""

import numpy as np
import polars as pl
import pytest

from schoolfactors.analysis import model


def _panel_one_school(z_by_year: dict[int, float], cds: str = "01000010000001",
                      n: int = 400) -> pl.DataFrame:
    rows = []
    for year, z in z_by_year.items():
        for test_id in (1, 2):
            rows.append({"cds": cds, "test_year": year, "grade": 5, "test_id": test_id,
                         "z": z, "var_z": 1.0 / n, "n": n})
    return pl.DataFrame(rows)


def test_level_is_recency_weighted_not_decade_average():
    # Steady decline from +1.0 to 0.0: the all-years average is ~0.5, but the
    # displayed level should sit near where the school scores now.
    years = {2015 + i: 1.0 - i * 0.125 for i in range(9)}  # 2023 -> 0.0
    eff = model.fit_school_models(_panel_one_school(years))
    assert len(eff) == 1
    level = eff["level"][0]
    assert level < 0.25, f"level {level:+.3f} still looks like a decade average"
    assert eff["last_year"][0] == 2023
    # Trend keeps the full window: the true slope is -0.125/yr.
    assert eff["trend"][0] == pytest.approx(-0.125, abs=0.01)


def test_flat_school_level_unchanged_by_weighting():
    years = {2015 + i: 0.4 for i in range(9)}
    eff = model.fit_school_models(_panel_one_school(years))
    assert eff["level"][0] == pytest.approx(0.4, abs=1e-6)


def test_adjust_lcb_matches_posterior_band():
    rng = np.random.default_rng(0)
    n = 200
    x = rng.uniform(0, 1, n)
    beta_true = -0.5
    lvl = beta_true * x + rng.normal(0, 0.2, n)
    df = pl.DataFrame({
        "cds": [f"{i:014d}" for i in range(n)],
        "level": lvl,
        "level_var": np.full(n, 0.01),
        "cov": x,
    })
    out, _coef, _tau2 = model.adjust(df, "level", ["cov"])
    eb = out["level_adj_eb"].to_numpy()
    lcb = out["level_adj_lcb"].to_numpy()
    lam = out["level_adj_reliability"].to_numpy()
    se = out["level_adj_se"].to_numpy()
    np.testing.assert_allclose(lcb, eb - 1.96 * np.sqrt(lam) * se, atol=1e-10)
    # The bound is strictly below the estimate and the band is nondegenerate.
    assert np.all(lcb < eb)
