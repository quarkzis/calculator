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


@pytest.mark.parametrize("task_code,affected_period", [
    ("OP_S6", "setup"), ("OP_S7", "setup"),
    ("OP_O5", "annual"), ("OP_O6", "annual"),
])
def test_low_risk_excludes_pending_risk_estimates_like_workbook(task_code, affected_period):
    # Working N14/N15 and N23/N24 use IF(country factor=0,0,task cost),
    # so a pending Article 10/11 estimate cannot make a low-risk cost TBC.
    edits = {task_code: {role: None for role in ROLES}}
    low = calculate(Settings(risk="low"), task_days=edits)
    assert_value(low.setup, 54921.41563636363)
    assert_value(low.annual, 25238.484818181816)
    assert not low.missing_inputs
    excluded = [row for row in low.details if row["code"] == task_code]
    assert all(row["input_days"] is None and row["effective_days"] == 0
               and row["final_cost"] == 0 for row in excluded)
    assert_detail_totals(low)
    high = calculate(Settings(), task_days=edits)
    assert getattr(high, affected_period) is None
    assert len(high.missing_inputs) == len(ROLES)
    table = build_scenario_table(task_days=edits)
    low_rows = [row for row in table if row["company"].startswith("operator_") and row["Risk"] == "Low"]
    assert low_rows and all(row["Status"] == "Calculated" for row in low_rows)
    high_rows = [row for row in table if row["company"].startswith("operator_") and row["Risk"] != "Low"]
    assert high_rows and all(row["Status"] == "TBC" for row in high_rows)


@pytest.mark.parametrize("settings,task_code", [
    (Settings(risk="low", size_factor=0), "OP_S1"),
    (Settings(dd_setup=0), "OP_S1"),
    (Settings(legality_share=1, retained_legality_share=0), "OP_O5"),
    (Settings(geolocation_enabled=False), "OP_S_GEO"),
    (Settings(company="downstream_non_sme", suppliers=0), "DN_S1"),
])
def test_zero_multiplier_does_not_resolve_a_pending_included_task(settings, task_code):
    result = calculate(settings, task_days={task_code: {"SO": None}})
    assert result.missing_inputs == (f"{task_code}: SO days",)
    assert result.total is None
    assert_detail_totals(result)


@pytest.mark.parametrize("phase,period", [("S", "setup"), ("O", "annual")])
def test_geolocation_off_excludes_its_row_but_still_needs_the_pool_allocation(phase, period):
    result = calculate(Settings(geolocation_enabled=False),
                       task_days={f"OP_{phase}_GEO": {"SO": None}})
    geo = next(row for row in result.details if row["code"] == f"OP_{phase}_GEO" and row["role"] == "SO")
    pool = next(row for row in result.details if row["code"] == f"OP_{phase}_INFO" and row["role"] == "SO")
    # Cost D12/D22 is 0 via the switch, but D11/D21 needs the allocation
    # to subtract it from the information pool even when geo is excluded.
    assert geo["input_days"] is None
    assert geo["effective_days"] == geo["base_cost"] == geo["final_cost"] == 0
    assert pool["effective_days"] is None and pool["final_cost"] is None
    assert getattr(result, period) is None
    assert getattr(result, "geo_setup" if phase == "S" else "geo_annual") is None
    assert result.missing_inputs == (f"OP_{phase}_GEO: SO days",)
    assert_detail_totals(result)


def test_custom_current_size_factor_is_shared_by_all_relevant_comparison_rows():
    settings = Settings(company="operator_small_micro", size="Small", size_factor=0.6,
                        complexity=2, commodity=2)
    table = build_scenario_table(settings=settings)
    lookup = {(row["case_id"], row["company"], row["Size"].lower()): row for row in table}
    for case in SCENARIOS:
        row = lookup[case["case_id"], case["group"], case["size"]]
        ratio = 0.6 / 0.75 if case["size"] == "small" and case["group"] in (
            "operator_small_micro", "downstream_sme",
        ) else 1
        for field, column in TABLE_FIELDS.items():
            expected = case["expected"][field]
            assert_value(row[column], expected if expected == "N/A" else expected * ratio)
    first = lookup["comparison_1", "operator_small_micro", "small"]
    assert_value(first["Setup (£)"], 189076.72145454545)
    assert_value(first["Annual (£)"], 81465.59425636363)
    assert_value(calculate(settings).setup, first["Setup (£)"])


@pytest.mark.parametrize("shared_sizes", [
    {"Large": 0.8, "Medium": 0.7, "Small": 0.6, "Micro": 0.25},
    {"Large": 0, "Medium": 0, "Small": 0, "Micro": 0},
])
def test_explicit_size_factors_apply_to_comparison_and_defra_without_scaling_exempt_groups(shared_sizes):
    # Explicit workbook factors supersede the selected company's custom value.
    table = build_scenario_table(settings=Settings(size_factor=0.123), size_factors=shared_sizes)
    lookup = {(row["case_id"], row["company"], row["Size"].lower()): row for row in table}
    original_sizes = {"large": 1, "medium": 0.9, "small": 0.75, "micro": 0.5}
    for case in SCENARIOS:
        row = lookup[case["case_id"], case["group"], case["size"]]
        ratio = 1 if case["group"] in ("primary", "downstream_non_sme") else (
            shared_sizes[case["size"].title()] / original_sizes[case["size"]]
        )
        for field, column in TABLE_FIELDS.items():
            expected = case["expected"][field]
            assert_value(row[column], expected if expected == "N/A" else expected * ratio)


def test_comparison_keeps_task_edits_and_volumes_for_all_company_families():
    # Independent worksheet sensitivity totals: double supplier and receipt
    # ratios together, using non-default reference counts for both groups.
    company_settings = {
        "downstream_non_sme": Settings(company="downstream_non_sme", suppliers=80,
            reference_suppliers=40, receipts=600, reference_receipts=300,
            geolocation_enabled=False, batch_dds=99, primary_complexity=9),
        "downstream_sme": Settings(company="downstream_sme", size="Medium", suppliers=40,
            reference_suppliers=20, receipts=300, reference_receipts=150,
            geolocation_enabled=False, batch_dds=99),
    }
    edits = {"OP_S1": {"SO": 31}, "P_S1": {"SO": 2},
             "DN_S1": {"SO": 3}, "DS_S1": {"SO": 2.5}}
    table = build_scenario_table(task_days=edits, company_settings=company_settings)
    lookup = {(r["case_id"], r["company"], r["Size"]): r for r in table}
    so_rate = 46262 * 1.22 / 220
    operator = lookup["comparison_1", "operator_large_medium", "Large"]
    assert_value(operator["Setup (£)"], 315127.8690909091 + so_rate * 4)
    assert_value(operator["Annual (£)"], 135775.9904272727)
    primary = lookup["comparison_2", "primary", "Small"]
    assert_value(primary["Setup (£)"], 676.5426818181818 + so_rate * 2 * 0.75)
    for case_id in ("comparison_1", "comparison_2", "comparison_3", "defra_1", "defra_6"):
        non_sme = lookup[case_id, "downstream_non_sme", "Large"]
        sme = lookup[case_id, "downstream_sme", "Medium"]
        assert_value(non_sme["Setup (£)"], 7966.166318181818 + so_rate * 2)
        assert_value(non_sme["Annual (£)"], 6686.642545454545)
        assert_value(sme["Setup (£)"], (2984.646818181818 + so_rate * 2) * 0.9)
        assert_value(sme["Annual (£)"], 3016.436136363636 * 0.9)
    # Selecting another company cannot change the saved workbook comparison.
    selected_other = Settings(company="primary", size="Small", risk="low")
    assert table == build_scenario_table(task_days=edits, settings=selected_other,
                                        company_settings=company_settings)


@pytest.mark.parametrize("kwargs", [
    {"size_factors": {"Small": -1}}, {"size_factors": {"Small": float("nan")}},
    {"size_factors": {"Unknown": 1}}, {"company_settings": {"unknown": Settings()}},
    {"company_settings": {"downstream_sme": {"suppliers": 20}}},
])
def test_invalid_shared_comparison_inputs_are_rejected(kwargs):
    with pytest.raises(ValueError):
        build_scenario_table(**kwargs)
