"""Parity against independently recalculated workbook cells, not engine internals."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from eudr_model import (
    COMPANY_GROUPS, COMPANY_SIZES, DEFAULT_DAY_RATES, ROLES, Settings,
    build_scenario_table, calculate, get_tasks,
)


WORKBOOK = json.loads((Path(__file__).parent / "fixtures/phase2_workbook.json").read_text(encoding="utf-8"))
SCENARIOS = WORKBOOK["scenario_cases"]
TOTAL_FIELDS = {"setup": "setup", "ongoing": "annual", "ongoing_year3": "annual_year3", "total_setup_plus_one_annual": "total"}
TABLE_FIELDS = {"setup": "Setup (£)", "ongoing": "Annual (£)", "ongoing_year3": "Annual year 3 (£)", "total_setup_plus_one_annual": "Setup + one annual (£)"}
WORKING_CASES = [
    ("operator_standard", "operator_large_medium", "Large", "standard_high"),
    ("operator_low", "operator_large_medium", "Large", "low"),
    ("operator_small_micro_standard", "operator_small_micro", "Small", "standard_high"),
    ("operator_small_micro_low", "operator_small_micro", "Small", "low"),
    ("primary", "primary", "Small", "low"),
    ("downstream_non_sme", "downstream_non_sme", "Large", "standard_high"),
    ("downstream_sme", "downstream_sme", "Medium", "standard_high"),
]


def assert_value(actual, expected):
    if expected == "N/A":
        assert actual is None
    else:
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-7)


def assert_detail_totals(result):
    if not result.eligible:
        return
    for phase, field in [("setup", "setup"), ("ongoing", "annual")]:
        costs = [row["final_cost"] for row in result.details if row["phase"] == phase]
        if any(value is None for value in costs):
            assert getattr(result, field) is None
        else:
            assert_value(sum(costs), getattr(result, field))


def scenario_settings(case):
    p = case["parameters"]
    return Settings(
        company=case["group"], size=case["size"].title(),
        risk="low" if case["risk"] == "low" else "standard_high",
        dd_setup=p["dd_setup"], dd_annual=p["dd_ongoing"],
        complexity=p["operator_complexity"], commodity=p["commodity_factor"],
        year3_efficiency=0.1 if p["year3_applies"] else None,
    )


def sensitivity_inputs(parameters, company="operator_large_medium", size="Large", risk="standard_high"):
    names = {
        "consignments_per_dds": "batch_dds", "land_use_retained": "retained_legality_share",
        "apply_local_laws_to_setup": "apply_legality_to_setup", "primary_micro_factor": "micro_ratio",
        "geolocation_enabled": "geolocation_enabled", "legality_share": "legality_share",
        "primary_complexity": "primary_complexity",
    }
    settings = {"company": company, "size": size, "risk": risk}
    for name, value in parameters.items():
        if name in names:
            settings[names[name]] = value
        elif name.startswith(company + "_"):
            settings[name[len(company) + 1:]] = value
    overrides = {
        ("OP_S_GEO" if phase == "setup" else "OP_O_GEO"): values
        for phase, values in parameters.get("geolocation_role_day_overrides", {}).items()
    }
    return Settings(**settings), overrides


def test_salary_rates_and_company_coverage_match_the_workbook():
    assert tuple(ROLES) == tuple(WORKBOOK["role_order"])
    assert DEFAULT_DAY_RATES == WORKBOOK["day_rates"]
    assert len(COMPANY_GROUPS) == 5
    observed = {(case["group"], case["size"].title()) for case in SCENARIOS}
    assert observed == {(group, size) for group, sizes in COMPANY_SIZES.items() for size in sizes}


@pytest.mark.parametrize("case", SCENARIOS, ids=lambda case: case["id"])
def test_every_workbook_scenario_cell(case):
    result = calculate(scenario_settings(case))
    assert result.eligible == (case["expected"]["setup"] != "N/A")
    for expected_key, field in TOTAL_FIELDS.items():
        assert_value(getattr(result, field), case["expected"][expected_key])
    assert_detail_totals(result)


def test_scenario_table_matches_all_90_workbook_rows():
    table = build_scenario_table()
    assert len(table) == 90
    lookup = {(row["case_id"], row["company"], row["Size"].lower()): row for row in table}
    assert len(lookup) == 90
    for case in SCENARIOS:
        row = lookup[case["case_id"], case["group"], case["size"]]
        for expected_key, field in TABLE_FIELDS.items():
            assert_value(row[field], case["expected"][expected_key])
        assert row["Status"] == ("N/A" if case["expected"]["setup"] == "N/A" else "Calculated")


@pytest.mark.parametrize("case", WORKBOOK["sensitivities"], ids=lambda case: case["id"])
def test_workbook_sensitivities_before_and_after_scenario_factors(case):
    expected = case["expected_working_totals"]
    for prefix, group, size, risk in WORKING_CASES:
        settings, overrides = sensitivity_inputs(case["parameters"], group, size, risk)
        result = calculate(settings, task_days=overrides)
        assert_value(result.base_setup, expected[prefix + "_setup"])
        assert_value(result.base_annual, expected[prefix + "_ongoing"])
        assert_detail_totals(result)
    operator_settings, overrides = sensitivity_inputs(case["parameters"])
    operator = calculate(operator_settings, task_days=overrides)
    assert_value(operator.geo_setup, expected["geolocation_setup"])
    assert_value(operator.geo_annual, expected["geolocation_ongoing"])
    dds_cost = sum(row["base_cost"] for row in operator.details if row["code"] in ("OP_O_DDS_FIXED", "OP_O_DDS_VARIABLE"))
    assert_value(dds_cost, expected["dds_submission_ongoing"])
    for phase in ("setup", "ongoing"):
        assert_value(sum(row["effective_days"] for row in operator.details if row["phase"] == phase), case["expected_operator_days"][phase])
    # A volume sensitivity belongs to its downstream group. It must not leak to the other group.
    changed_group = next((group for group in ("downstream_non_sme", "downstream_sme")
                          if any(key.startswith(group + "_") for key in case["parameters"])), "operator_large_medium")
    settings, overrides = sensitivity_inputs(case["parameters"], changed_group, COMPANY_SIZES[changed_group][0])
    table = {(row["case_id"], row["company"], row["Size"].lower()): row for row in build_scenario_table(settings=settings, task_days=overrides)}
    for scenario in SCENARIOS:
        for field, cell in scenario["cells"].items():
            if cell in case["expected_scenario_cells"]:
                actual = table[scenario["case_id"], scenario["group"], scenario["size"]][TABLE_FIELDS[field]]
                assert_value(actual, case["expected_scenario_cells"][cell])


def test_geolocation_allocation_does_not_double_count_and_off_removes_it():
    base = calculate(Settings())
    changed = {"OP_S_GEO": {"SO": 12.0}, "OP_O_GEO": {"SO": 8.0}}
    included = calculate(Settings(), task_days=changed)
    excluded = calculate(Settings(geolocation_enabled=False), task_days=changed)
    assert_value(included.setup, base.setup)
    assert_value(included.annual, base.annual)
    assert_value(included.setup - excluded.setup, included.geo_setup)
    assert_value(included.annual - excluded.annual, included.geo_annual)
    with pytest.raises(ValueError, match="geolocation"):
        calculate(Settings(), task_days={"OP_S_GEO": {"SO": 21}})


def test_dds_batching_keeps_fixed_effort():
    result = calculate(Settings(batch_dds=4))
    fixed = [row for row in result.details if row["code"] == "OP_O_DDS_FIXED"]
    variable = [row for row in result.details if row["code"] == "OP_O_DDS_VARIABLE"]
    assert sum(row["effective_days"] for row in fixed) == 6
    assert sum(row["effective_days"] for row in variable) == 1.5
    very_large_batch = calculate(Settings(batch_dds=1e9))
    fixed_after = [row for row in very_large_batch.details if row["code"] == "OP_O_DDS_FIXED"]
    assert fixed == fixed_after


def test_local_laws_and_low_risk_apply_only_to_the_risk_tasks():
    base = calculate(Settings())
    full_laws = calculate(Settings(retained_legality_share=1))
    setup_reduced = calculate(Settings(apply_legality_to_setup=True))
    low_risk = calculate(Settings(risk="low"))
    risk_codes = {task.code for task in get_tasks("operator_large_medium") if task.excel_row in (13, 14, 23, 24)}
    assert len(risk_codes) == 4
    for current, full, setup, low in zip(base.details, full_laws.details, setup_reduced.details, low_risk.details):
        is_risk = current["code"] in risk_codes
        assert_value(current["base_cost"], full["base_cost"] * (0.775 if is_risk and current["phase"] == "ongoing" else 1))
        assert_value(setup["base_cost"], full["base_cost"] * (0.775 if is_risk else 1))
        assert_value(low["base_cost"], 0 if is_risk else full["base_cost"])


@pytest.mark.parametrize("group,size", [("primary", "Small"), ("primary", "Micro"), ("downstream_non_sme", "Large"), ("downstream_sme", "Medium")])
def test_new_groups_ignore_operator_dd_commodity_and_complexity(group, size):
    settings = Settings(company=group, size=size, risk="low")
    original = calculate(settings)
    changed = calculate(replace(settings, dd_setup=0.1, dd_annual=0.3, complexity=9, commodity=7))
    assert_value(changed.setup, original.setup)
    assert_value(changed.annual, original.annual)
    if group == "primary":
        no_generic_size = calculate(replace(settings, size_factor=0.1))
        assert_value(no_generic_size.setup, original.setup)
        assert_value(no_generic_size.annual, original.annual)


@pytest.mark.parametrize("group,size,reference,rows", [
    ("downstream_non_sme", "Large", (50, 400), {51, 59, 60}),
    ("downstream_sme", "Medium", (30, 200), {69, 76, 77}),
])
def test_downstream_volume_changes_affect_only_named_task_rows(group, size, reference, rows):
    settings = Settings(company=group, size=size)
    base = calculate(settings)
    doubled = calculate(replace(settings, suppliers=reference[0] * 2, receipts=reference[1] * 2))
    source_rows = {task.code: task.excel_row for task in get_tasks(group)}
    for before, after in zip(base.details, doubled.details):
        expected_multiplier = 2 if source_rows[before["code"]] in rows else 1
        assert_value(after["final_cost"], before["final_cost"] * expected_multiplier)
    zero_volume = calculate(replace(settings, suppliers=0, receipts=0))
    assert zero_volume.setup > 0 and zero_volume.annual > 0


def test_blank_role_days_keep_period_pending_and_zero_is_a_valid_estimate():
    settings = Settings(company="primary", size="Small", risk="low")
    first_task = next(task for task in get_tasks("primary") if task.excel_row == 39)
    missing = calculate(settings, task_days={first_task.code: {"SO": None}})
    assert missing.setup is None and missing.total is None
    assert_value(missing.annual, 256.10953977272726)
    assert missing.missing_inputs
    assert_detail_totals(missing)
    zero_days = {task.code: {role: 0 for role in ROLES} for task in get_tasks("primary")}
    zero = calculate(settings, task_days=zero_days)
    assert (zero.setup, zero.annual, zero.annual_year3, zero.total) == (0, 0, 0, 0)
    assert not zero.missing_inputs
    ineligible = calculate(replace(settings, risk="standard_high"), task_days=zero_days)
    assert not ineligible.eligible and ineligible.setup is None and ineligible.annual is None


@pytest.mark.parametrize("settings", [
    Settings(batch_dds=0), Settings(legality_share=None), Settings(retained_legality_share=1.1),
    Settings(company="downstream_non_sme", reference_suppliers=0),
    Settings(company="downstream_sme", size="Medium", receipts=-1),
    Settings(company="downstream_sme", size="Medium", suppliers=1.5),
    Settings(year3_efficiency=1.1),
])
def test_invalid_controls_cannot_return_a_misleading_cost(settings):
    with pytest.raises(ValueError):
        calculate(settings)


@pytest.mark.parametrize("invalid", [-1, float("nan"), float("inf"), "2", True])
def test_invalid_role_days_and_day_rates_are_rejected(invalid):
    with pytest.raises(ValueError):
        calculate(Settings(), task_days={"OP_S1": {"SO": invalid}})
    with pytest.raises(ValueError):
        calculate(Settings(), day_rates={"SO": invalid})
