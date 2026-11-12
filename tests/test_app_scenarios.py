"""The main screen must identify and reproduce the selected Excel scenario.

Expected results and cells come from the independently recalculated workbook
fixture, not from the app's scenario-selection implementation.
"""

import pytest

from test_app import (
    WORKBOOK, assert_cost, assert_report_matches_screen, make_app, metric,
    report_rows,
)


@pytest.fixture
def workbook_app(monkeypatch):
    return make_app(monkeypatch)


FIELDS = (
    ("setup", "Set-up cost GBP", "Set-up cost"),
    ("ongoing", "Annual cost GBP", "Annual cost"),
    ("ongoing_year3", "Annual cost from year 3 GBP", "Annual cost from year 3"),
    ("total_setup_plus_one_annual", "Set-up plus one annual cost GBP", "Set-up + one annual cost"),
)


def summary(downloads):
    return {row["Item"]: row["Value"] for row in report_rows(downloads)
            if row["Section"] == "Summary"}


def assert_workbook_case(at, downloads, case):
    assert not at.exception, case["id"]
    exported = summary(downloads)
    for expected_key, report_key, metric_key in FIELDS:
        expected = case["expected"][expected_key]
        actual = exported[report_key]
        if isinstance(expected, str):
            assert actual == expected, (case["id"], expected_key)
            assert metric(at, metric_key) == expected
        else:
            assert float(actual) == pytest.approx(expected, abs=1e-7), (case["id"], expected_key)
            assert metric(at, metric_key) == f"£{float(actual):,.2f}"
    all_values = " ".join(str(row["Value"]) for row in report_rows(downloads))
    assert case["sheet"] in all_values
    for cell in case["cells"].values():
        assert cell in all_values, (case["id"], cell)


def test_default_screen_is_defra_4_and_identifies_its_excel_cells(workbook_app):
    at, downloads = workbook_app
    assert at.selectbox(key="scenario_id").value == "defra_4"
    assert_cost(at, 59086.47545454545, 25457.998205113632)
    assert metric(at, "Annual cost from year 3") == "£22,912.20"
    assert metric(at, "Set-up + one annual cost") == "£84,544.47"
    case = next(item for item in WORKBOOK["scenario_cases"]
                if item["id"] == "defra_4__operator_large_medium__large")
    assert_workbook_case(at, downloads, case)
    visible = " ".join(item.value for kind in (at.caption, at.markdown, at.info) for item in kind)
    assert "Defra 4" in visible
    assert "D41" in visible and "E41" in visible
    assert_report_matches_screen(at, downloads)


def test_main_screen_matches_all_90_workbook_scenarios(workbook_app):
    at, downloads = workbook_app
    # One authenticated session also exercises transitions between scenarios,
    # groups and sizes; separate fresh apps would miss retained-state bugs.
    cases = sorted(WORKBOOK["scenario_cases"],
                   key=lambda case: (case["group"], case["size"], case["case_id"]))
    assert len(cases) == 90
    for case in cases:
        group, size = case["group"], case["size"].title()
        if at.selectbox(key="company_group").value != group:
            at.selectbox(key="company_group").set_value(group).run()
        if at.selectbox(key=f"size:{group}").value != size:
            at.selectbox(key=f"size:{group}").set_value(size).run()
        at.selectbox(key="scenario_id").set_value(case["case_id"]).run()
        assert_workbook_case(at, downloads, case)


def test_working_base_is_explicit_and_year3_is_not_applicable(workbook_app):
    at, downloads = workbook_app
    at.selectbox(key="scenario_id").set_value("working_base").run()
    assert_cost(at, 78781.96727272727, 33943.99760681818)
    assert metric(at, "Annual cost from year 3") == "N/A"
    exported = summary(downloads)
    assert exported["Annual cost from year 3 GBP"] == "N/A"
    all_values = " ".join(str(row["Value"]) for row in report_rows(downloads))
    assert "Working_table (Phase 2)" in all_values
    assert "I17" in all_values and "I27" in all_values
    assert_report_matches_screen(at, downloads)


def test_named_scenarios_preserve_task_edits_and_custom_assumptions(workbook_app):
    at, downloads = workbook_app
    group = "operator_large_medium"
    at.selectbox(key="scenario_id").set_value("custom").run()
    at.selectbox(key=f"dd:{group}").set_value("Partial existing due diligence").run()
    at.number_input(key=f"complexity_factor:{group}:Standard").set_value(1.25)
    at.number_input(key=f"batch:{group}").set_value(8.0)
    at.number_input(key=f"_days:{group}:OP_S1:SO").set_value(31.0).run()
    custom_setup = metric(at, "Set-up cost")
    custom_annual = metric(at, "Annual cost")

    at.selectbox(key="scenario_id").set_value("comparison_1").run()
    so = 46262 * 1.22 / 220
    aa = 29425 * 1.22 / 220
    base_setup = 78781.96727272727 + so
    base_annual = 33943.99760681818 + (1 / 8 - 1 / 4) * (2 * so + 4 * aa)
    assert_cost(at, base_setup * 4, base_annual * 4)
    assert metric(at, "Annual cost from year 3") == "N/A"
    assert at.number_input(key=f"_days:{group}:OP_S1:SO").value == 31
    assert at.number_input(key=f"batch:{group}").value == 8

    at.selectbox(key="scenario_id").set_value("defra_4").run()
    assert_cost(at, base_setup * 0.75, base_annual * 0.75)
    at.selectbox(key="scenario_id").set_value("custom").run()
    assert metric(at, "Set-up cost") == custom_setup
    assert metric(at, "Annual cost") == custom_annual
    assert at.number_input(key=f"complexity_factor:{group}:Standard").value == 1.25
    assert at.selectbox(key=f"dd:{group}").value == "Partial existing due diligence"
    assert_report_matches_screen(at, downloads)


def test_year3_na_is_distinct_from_a_pending_annual_estimate(workbook_app):
    at, downloads = workbook_app
    at.selectbox(key="scenario_id").set_value("comparison_1").run()
    key = "_days:operator_large_medium:OP_O1:SO"
    at.number_input(key=key).set_value(None).run()
    assert metric(at, "Annual cost") == "TBC"
    assert metric(at, "Annual cost from year 3") == "N/A"
    assert summary(downloads)["Annual cost from year 3 GBP"] == "N/A"

    at.selectbox(key="scenario_id").set_value("comparison_2").run()
    assert metric(at, "Annual cost") == "TBC"
    assert metric(at, "Annual cost from year 3") == "TBC"
    assert summary(downloads)["Annual cost from year 3 GBP"] == "TBC"

    at.number_input(key=key).set_value(5.0).run()
    case = next(item for item in WORKBOOK["scenario_cases"]
                if item["id"] == "comparison_2__operator_large_medium__large")
    assert_workbook_case(at, downloads, case)
    at.selectbox(key="scenario_id").set_value("comparison_3").run()
    assert metric(at, "Annual cost from year 3") == "N/A"
    assert_report_matches_screen(at, downloads)


def test_defra_controls_update_the_named_result_and_comparison_together(workbook_app):
    at, downloads = workbook_app
    at.number_input(key="defra_dd_setup").set_value(0.5)
    at.number_input(key="defra_dd_annual").set_value(0.6)
    at.number_input(key="defra_complexity").set_value(1.25)
    at.number_input(key="year3_efficiency_percent").set_value(25.0).run()
    setup = 78781.96727272727 * 0.5 * 1.25
    annual = 33943.99760681818 * 0.6 * 1.25
    assert_cost(at, setup, annual)
    assert metric(at, "Annual cost from year 3") == f"£{annual * 0.75:,.2f}"
    table = at.dataframe[-1].value
    row = table.loc[(table["Company"] == "Operator (large / medium)")
                    & (table["Size"] == "Large")
                    & (table["Scenario"] == "Defra 4")].iloc[0]
    assert row["Setup (£)"] == pytest.approx(setup)
    assert row["Annual (£)"] == pytest.approx(annual)
    assert row["Annual year 3 (£)"] == pytest.approx(annual * 0.75)
    assert_report_matches_screen(at, downloads)
    # Comparison 2 keeps its own 10% convention even after Defra is edited.
    at.selectbox(key="scenario_id").set_value("comparison_2").run()
    case = next(item for item in WORKBOOK["scenario_cases"]
                if item["id"] == "comparison_2__operator_large_medium__large")
    assert_workbook_case(at, downloads, case)
