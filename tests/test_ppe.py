"""ESSA per-pupil expenditure normalization (analysis/export.normalize_ppe_year)."""

from __future__ import annotations

from schoolfactors.analysis.export import normalize_ppe_year

DIST = "19643370000000"  # a district LEA
CHARTER = "19643370131573"  # a direct-funded charter LEA (its own 14-digit code)


def _row(scds, lea, pp, mem=None):
    return ("essappe2425data", scds, lea, pp, mem)


def _no_enr(_scds, _year):
    return None


def test_consistent_district_is_kept():
    rows = [_row("19643371931187", DIST, 16_000, 2_000), _row("19643376011878", DIST, 17_000, 500)]
    values, flagged = normalize_ppe_year(rows, 2025, _no_enr, {(2025, "64337"): 16_445.0})
    assert flagged == {}
    assert values["19643371931187"] == (16_000, 2_000)


def test_district_far_below_current_expense_is_dropped_entirely():
    # Burbank 2024-25: school-site ~$8.4k + $387 central at every school,
    # against $16,445 per ADA — every row goes, even the plausible ones.
    rows = [
        _row("19643371931187", DIST, 8_011, 2_457),
        _row("19643376011878", DIST, 9_720, 419),
        _row("19643371933332", DIST, 25_836, 91),  # continuation: high but real
    ]
    values, flagged = normalize_ppe_year(rows, 2025, _no_enr, {(2025, "64337"): 16_445.0})
    assert list(flagged) == [DIST] and 0.5 < flagged[DIST] < 0.6
    assert values == {}


def test_district_far_above_current_expense_is_dropped():
    rows = [_row("19643371931187", DIST, 40_000, 2_000)]
    values, flagged = normalize_ppe_year(rows, 2025, _no_enr, {(2025, "64337"): 16_445.0})
    assert flagged == {DIST: 2.43} and values == {}


def test_charter_lea_and_district_without_current_expense_are_not_checked():
    rows = [
        _row("19643370131573", CHARTER, 6_000, 300),
        _row("19643371931187", DIST, 40_000, 2_000),
    ]
    values, flagged = normalize_ppe_year(rows, 2025, _no_enr, {})
    assert flagged == {}
    assert set(values) == {"19643370131573", "19643371931187"}


def test_totals_reporter_is_divided_before_the_cross_check():
    # An LEA that filed total dollars: 33M / 2000 = $16.5k, consistent.
    rows = [_row("19643371931187", DIST, 33_000_000, 2_000), _row("19643376011878", DIST, 8_000_000, 500)]
    values, flagged = normalize_ppe_year(rows, 2025, _no_enr, {(2025, "64337"): 16_445.0})
    assert flagged == {}
    assert values["19643371931187"] == (16_500, 2_000)


def test_broken_lea_and_out_of_range_rows_are_dropped():
    rows = [
        _row("19643371931187", DIST, 1_000, 2_000),
        _row("19643376011878", DIST, 900, 500),
        _row("19643370131573", CHARTER, 700_000, 300),
    ]
    values, flagged = normalize_ppe_year(rows, 2025, _no_enr, {(2025, "64337"): 16_445.0})
    assert values == {} and flagged == {}


def test_census_enrollment_stands_in_for_missing_membership():
    rows = [_row("19643371931187", DIST, 16_000, None)]
    values, flagged = normalize_ppe_year(
        rows, 2019, lambda s, y: 2_000 if (s, y) == ("19643371931187", 2019) else None,
        {(2019, "64337"): 11_633.0},
    )
    assert values["19643371931187"] == (16_000, 2_000) and flagged == {}
