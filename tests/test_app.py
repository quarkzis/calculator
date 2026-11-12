"""Exercise real Streamlit reruns and the reports offered by the interface."""

import csv
from io import StringIO
import json
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = json.loads((ROOT / "tests/fixtures/phase2_workbook.json").read_text(encoding="utf-8"))


def make_app(monkeypatch):
    """Open the real default UI with a synthetic credential and capture CSVs."""
    downloads = {}
    original = st.download_button

    def capture_download(*args, **kwargs):
        downloads[kwargs["key"]] = kwargs["data"]
        return original(*args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture_download)
    at = AppTest.from_file(ROOT / "calculator.py", default_timeout=30)
    # Synthetic public test credential; this always overrides any local secrets.
    at.secrets["app_password_hash"] = (
        "pbkdf2_sha256$600000$00112233445566778899aabbccddeeff$"
        "a6f7eba8762b50fb319b7eb8101847f6aa4a2951fba5a8f687938057b5f7cbf3"
    )
    at.run()
    assert not at.exception
    at.text_input(key="_access_password").set_value("Contraseña para pruebas 🔒")
    at.button(key="_access_submit").click().run()
    assert not at.exception
    return at, downloads


@pytest.fixture
def app(monkeypatch):
    # These regression workflows exercise freely editable assumptions. Named
    # workbook scenarios and the new default are covered in test_app_scenarios.
    at, downloads = make_app(monkeypatch)
    at.selectbox(key="scenario_id").set_value("custom").run()
    assert not at.exception
    return at, downloads


def metric(at, label):
    return next(item.value for item in at.metric if item.label == label)


def assert_cost(at, setup, annual):
    assert not at.exception
    assert metric(at, "Set-up cost") == f"£{setup:,.2f}"
    assert metric(at, "Annual cost") == f"£{annual:,.2f}"


def report_rows(downloads):
    data = downloads["download_current"]
    return list(csv.DictReader(StringIO(data.decode("utf-8-sig") if isinstance(data, bytes) else data)))


def assert_report_matches_screen(at, downloads):
    rows = report_rows(downloads)
    summary = {row["Item"]: row["Value"] for row in rows if row["Section"] == "Summary"}
    for name, label in [("Set-up cost GBP", "Set-up cost"), ("Annual cost GBP", "Annual cost"),
                        ("Annual cost from year 3 GBP", "Annual cost from year 3"),
                        ("Set-up plus one annual cost GBP", "Set-up + one annual cost")]:
        value = summary[name]
        expected = value if value in ("TBC", "N/A") else f"£{float(value):,.2f}"
        assert metric(at, label) == expected
    if summary["Status"] == "Complete":
        detail = [row for row in rows if row["Section"] == "Cost detail"]
        for phase, name in [("Set-up", "Set-up cost GBP"), ("Annual", "Annual cost GBP")]:
            assert sum(float(row["Final cost GBP"]) for row in detail if row["Period"] == phase) == pytest.approx(float(summary[name]), abs=1e-7)
        visible = next(item.value for item in at.dataframe if "Day rate (£)" in item.value.columns)
        for phase in visible["Period"].unique():
            assert visible.loc[visible["Period"] == phase, "Final cost (£)"].sum() == pytest.approx(
                sum(float(row["Final cost GBP"]) for row in detail if row["Period"] == phase), abs=1e-7
            )
    scenarios = pd.read_csv(StringIO(downloads["download_scenarios"].decode("utf-8-sig")))
    shown = at.dataframe[-1].value
    assert len(scenarios) == len(shown) == 90
    # Compare the downloaded table to the actual visible dataframe, including N/A cells.
    expected = pd.read_csv(StringIO(shown.to_csv(index=False)))
    pd.testing.assert_frame_equal(scenarios, expected, check_dtype=False)


def test_all_company_groups_match_workbook_and_downloads(app):
    at, downloads = app
    cases = [
        ("operator_large_medium", 78781.96727272727, 33943.99760681818),
        ("operator_small_micro", 59086.47545454545, 25457.998205113636),
        ("primary", 676.5426818181818, 256.10953977272726),
        ("downstream_non_sme", 6312.458272727272, 4082.425),
        ("downstream_sme", 2192.9904818181817, 1592.1549),
    ]
    for group, setup, annual in cases:
        at.selectbox(key="company_group").set_value(group).run()
        assert_cost(at, setup, annual)
        assert_report_matches_screen(at, downloads)
        keys = [widget.key for kind in (at.selectbox, at.number_input, at.checkbox, at.radio) for widget in kind]
        assert len(keys) == len(set(keys))


def test_factor_choices_reset_to_their_presets_and_rates_keep_precision(app):
    at, downloads = app
    company = "operator_large_medium"
    at.selectbox(key=f"size:{company}").set_value("Medium")
    at.selectbox(key=f"dd:{company}").set_value("Partial existing due diligence")
    at.selectbox(key=f"complexity_choice:{company}").set_value("Complex")
    at.selectbox(key=f"commodity_choice:{company}").set_value(1.5).run()
    assert at.number_input(key=f"size_factor:{company}:Medium").value == 0.9
    assert at.number_input(key=f"dd_setup:{company}:Partial existing due diligence").value == 0.75
    assert at.number_input(key=f"dd_annual:{company}:Partial existing due diligence").value == 0.75
    assert at.number_input(key=f"complexity_factor:{company}:Complex").value == 2
    assert at.number_input(key=f"commodity_factor:{company}:1.5").value == 1.5
    assert_cost(at, 159533.48372727272, 68736.59515380681)
    assert_report_matches_screen(at, downloads)
    at.selectbox(key=f"dd:{company}").set_value("Full existing due diligence").run()
    assert at.number_input(key=f"dd_setup:{company}:Full existing due diligence").value == 0.5
    assert at.number_input(key=f"dd_annual:{company}:Full existing due diligence").value == 1
    at.selectbox(key=f"size:{company}").set_value("Large")
    at.selectbox(key=f"dd:{company}").set_value("No existing due diligence")
    at.selectbox(key=f"complexity_choice:{company}").set_value("Standard")
    at.selectbox(key=f"commodity_choice:{company}").set_value(1.0).run()
    assert_cost(at, 78781.96727272727, 33943.99760681818)
    at.radio(key="task_period").set_value("Annual only").run()
    for role, rate in WORKBOOK["day_rates"].items():
        assert at.number_input(key=f"rate:{role}").value == rate
    exported_rates = {row["Role"]: float(row["Value"]) for row in report_rows(downloads) if row["Section"] == "Day rates"}
    assert exported_rates == WORKBOOK["day_rates"]


def test_missing_zero_eligibility_and_task_edits_survive_hidden_widgets(app):
    at, downloads = app
    at.selectbox(key="company_group").set_value("primary").run()
    day_widgets = [widget for widget in at.number_input if widget.key.startswith("_days:primary:")]
    changed_key = day_widgets[0].key
    original_value = day_widgets[0].value
    at.number_input(key=changed_key).set_value(None).run()
    assert not at.exception
    assert metric(at, "Set-up cost") == "TBC"
    assert metric(at, "Annual cost") == "£256.11"
    assert_report_matches_screen(at, downloads)
    at.radio(key="task_period").set_value("Annual only").run()
    at.selectbox(key="company_group").set_value("downstream_sme").run()
    at.selectbox(key="company_group").set_value("primary").run()
    at.radio(key="task_period").set_value("Both periods").run()
    assert at.number_input(key=changed_key).value is None
    assert metric(at, "Set-up cost") == "TBC"
    at.number_input(key=changed_key).set_value(original_value).run()
    assert_cost(at, 676.5426818181818, 256.10953977272726)
    for widget in at.number_input:
        if widget.key.startswith("_days:primary:"):
            widget.set_value(0.0)
    at.run()
    assert_cost(at, 0, 0)
    assert_report_matches_screen(at, downloads)
    at.selectbox(key="risk:primary").set_value("standard_high").run()
    assert not at.exception
    assert metric(at, "Set-up cost") == "N/A"
    assert metric(at, "Annual cost") == "N/A"
    assert_report_matches_screen(at, downloads)


def test_defra_controls_change_comparison_cases_without_changing_current_cost(app):
    at, downloads = app
    at.number_input(key="defra_dd_setup").set_value(0.5)
    at.number_input(key="defra_dd_annual").set_value(0.6)
    at.number_input(key="defra_complexity").set_value(1.25).run()
    assert_cost(at, 78781.96727272727, 33943.99760681818)
    assert_report_matches_screen(at, downloads)
    exported_settings = {row["Item"]: row["Value"] for row in report_rows(downloads) if row["Section"] == "Settings"}
    assert float(exported_settings["defra_dd_setup"]) == 0.5
    assert float(exported_settings["defra_dd_annual"]) == 0.6
    assert float(exported_settings["defra_complexity"]) == 1.25
    table = at.dataframe[-1].value
    operator = table.loc[(table["Company"] == "Operator (large / medium)") & (table["Size"] == "Large")]
    defra = operator.loc[operator["Scenario"] == "Defra 1"].iloc[0]
    working = WORKBOOK["expected_working_totals"]
    assert defra["Setup (£)"] == pytest.approx(working["operator_low_setup"]["value"] * 0.5 * 1.25)
    assert defra["Annual (£)"] == pytest.approx(working["operator_low_ongoing"]["value"] * 0.6 * 1.25)
    comparison = operator.loc[operator["Scenario"] == "Scenario 1"].iloc[0]
    expected = next(case["expected"] for case in WORKBOOK["scenario_cases"] if case["id"] == "comparison_1__operator_large_medium__large")
    assert comparison["Setup (£)"] == pytest.approx(expected["setup"])
    assert comparison["Annual (£)"] == pytest.approx(expected["ongoing"])
