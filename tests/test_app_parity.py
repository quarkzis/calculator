"""Regression workflows for a single shared, editable workbook in the app.

Expected amounts below use the independently checked 9 November workbook
totals and explicit role-day deltas, rather than calling the app's engine.
"""

import pytest

from test_app import app, assert_cost, assert_report_matches_screen, metric, report_rows


SO = 46262 * 1.22 / 220
LAW = 50856 * 1.22 / 220
PM = 42871 * 1.22 / 220
AA = 29425 * 1.22 / 220
IT = 36775 * 1.22 / 220
OP_SETUP = 78781.96727272727
OP_ANNUAL = 33943.99760681818
PRIMARY_SETUP = 902.0569090909091
PRIMARY_ANNUAL = 341.47938636363637
DN_SETUP = 6312.458272727272
DN_ANNUAL = 4082.425
DS_SETUP = 2436.656090909091
DS_ANNUAL = 1769.061


def scenario(at, company, size, name="Comparison 2"):
    assert not at.exception
    table = at.dataframe[-1].value
    match = table.loc[
        (table["Company"] == company)
        & (table["Size"] == size)
        & (table["Scenario"] == name)
    ]
    assert len(match) == 1
    return match.iloc[0]


def assert_scenario(at, company, size, setup, annual, name="Comparison 2"):
    row = scenario(at, company, size, name)
    assert row["Setup (£)"] == pytest.approx(setup, abs=1e-7)
    assert row["Annual (£)"] == pytest.approx(annual, abs=1e-7)
    assert row["Status"] == "Calculated"


def test_operator_task_edits_are_shared_and_survive_switching_groups(app):
    at, downloads = app
    large = "operator_large_medium"
    small = "operator_small_micro"
    at.number_input(key=f"_days:{large}:OP_S1:SO").set_value(31.0).run()
    assert_cost(at, OP_SETUP + SO, OP_ANNUAL)

    at.selectbox(key="company_group").set_value(small).run()
    assert at.number_input(key=f"_days:{small}:OP_S1:SO").value == 31
    assert_cost(at, (OP_SETUP + SO) * 0.75, OP_ANNUAL * 0.75)
    at.number_input(key=f"_days:{small}:OP_S1:SO").set_value(32.0).run()
    at.selectbox(key="company_group").set_value("primary").run()
    assert_scenario(at, "Operator (large / medium)", "Large",
                    (OP_SETUP + 2 * SO) * 4, OP_ANNUAL * 4, "Comparison 1")

    at.selectbox(key="company_group").set_value(large).run()
    assert at.number_input(key=f"_days:{large}:OP_S1:SO").value == 32
    assert_cost(at, OP_SETUP + 2 * SO, OP_ANNUAL)
    assert_report_matches_screen(at, downloads)


def test_operator_controls_remain_shared_when_hidden(app):
    at, downloads = app
    group = "operator_large_medium"
    at.checkbox(key=f"geo:{group}").uncheck()
    at.number_input(key=f"batch:{group}").set_value(8.0)
    at.number_input(key=f"legality:{group}").set_value(40.0)
    at.number_input(key=f"retained:{group}").set_value(20.0)
    at.checkbox(key=f"setup_legality:{group}").check().run()

    legal_factor = 1 - 0.4 * (1 - 0.2)
    geo_setup = 10 * SO + 9 * PM + 6 * AA + 4 * IT + 4 * 800
    geo_annual = 6 * SO + 4 * PM + 4 * AA
    risk_setup = 24 * SO + 3 * LAW + 17 * PM + 5 * AA + 15 * 800
    risk_annual = 18 * SO + 11 * PM + 5 * 800
    setup = OP_SETUP - geo_setup + (legal_factor - 1) * risk_setup
    annual = (OP_ANNUAL - geo_annual
              + (1 / 8 - 1 / 4) * (2 * SO + 4 * AA)
              + (legal_factor - 0.775) * risk_annual)
    assert_cost(at, setup, annual)

    at.selectbox(key="company_group").set_value("primary").run()
    assert_scenario(at, "Operator (large / medium)", "Large",
                    setup * 4, annual * 4, "Comparison 1")
    small = "operator_small_micro"
    at.selectbox(key="company_group").set_value(small).run()
    assert not at.checkbox(key=f"geo:{small}").value
    assert at.number_input(key=f"batch:{small}").value == 8
    assert at.number_input(key=f"legality:{small}").value == 40
    assert at.number_input(key=f"retained:{small}").value == 20
    assert at.checkbox(key=f"setup_legality:{small}").value
    assert_cost(at, setup * 0.75, annual * 0.75)
    at.selectbox(key="company_group").set_value(group).run()
    assert_cost(at, setup, annual)
    assert_report_matches_screen(at, downloads)


def test_primary_micro_and_complexity_controls_stay_active_for_all_views(app):
    at, downloads = app
    at.selectbox(key="company_group").set_value("primary").run()
    at.selectbox(key="size:primary").set_value("Micro").run()
    at.number_input(key="primary_complexity").set_value(0.6)
    at.number_input(key="primary_micro_ratio").set_value(0.75)
    at.number_input(key="_days:primary:P_S1:SO").set_value(2.0).run()
    setup = (PRIMARY_SETUP + 2 * SO) * 0.6
    annual = PRIMARY_ANNUAL * 0.6
    assert_cost(at, setup * 0.75, annual * 0.75)

    at.selectbox(key="size:primary").set_value("Small").run()
    assert_cost(at, setup, annual)
    assert_scenario(at, "Primary operator (small / micro)", "Micro",
                    setup * 0.75, annual * 0.75)
    at.selectbox(key="company_group").set_value("downstream_sme").run()
    assert_scenario(at, "Primary operator (small / micro)", "Small", setup, annual)
    assert_scenario(at, "Primary operator (small / micro)", "Micro",
                    setup * 0.75, annual * 0.75)
    at.selectbox(key="company_group").set_value("primary").run()
    at.selectbox(key="size:primary").set_value("Micro").run()
    assert at.number_input(key="primary_micro_ratio").value == 0.75
    assert at.number_input(key="primary_complexity").value == 0.6
    assert_cost(at, setup * 0.75, annual * 0.75)
    assert_report_matches_screen(at, downloads)


def test_custom_size_factor_changes_comparisons_and_other_groups(app):
    at, downloads = app
    group = "operator_small_micro"
    at.selectbox(key="company_group").set_value(group).run()
    at.number_input(key=f"size_factor:{group}:Small").set_value(0.6).run()
    assert_cost(at, OP_SETUP * 0.6, OP_ANNUAL * 0.6)
    assert_scenario(at, "Operator (small / micro)", "Small",
                    OP_SETUP * 4 * 0.6, OP_ANNUAL * 4 * 0.6, "Comparison 1")
    assert_scenario(at, "Operator (small / micro)", "Small",
                    OP_SETUP * 0.75 * 0.6, OP_ANNUAL * 0.75 * 0.6,
                    "Defra standard/high risk, commodity factor 1")
    assert_scenario(at, "Downstream (SME)", "Small", DS_SETUP * 0.6, DS_ANNUAL * 0.6)

    at.selectbox(key="company_group").set_value("downstream_sme").run()
    at.selectbox(key="size:downstream_sme").set_value("Small").run()
    assert at.number_input(key="size_factor:downstream_sme:Small").value == 0.6
    assert_cost(at, DS_SETUP * 0.6, DS_ANNUAL * 0.6)
    at.number_input(key="size_factor:downstream_sme:Small").set_value(0.0).run()
    assert_cost(at, 0, 0)
    assert_scenario(at, "Operator (small / micro)", "Small", 0, 0, "Comparison 1")
    assert_report_matches_screen(at, downloads)


def test_all_group_edits_and_both_downstream_volumes_feed_one_comparison(app):
    at, downloads = app
    at.selectbox(key="company_group").set_value("primary").run()
    at.number_input(key="_days:primary:P_S1:SO").set_value(2.0).run()

    group = "downstream_non_sme"
    at.selectbox(key="company_group").set_value(group).run()
    at.number_input(key=f"_days:{group}:DN_S2:SO").set_value(4.0)
    at.number_input(key=f"suppliers:{group}").set_value(100)
    at.number_input(key=f"receipts:{group}").set_value(800).run()
    dn_setup = DN_SETUP + (2 * SO + 2 * PM + AA + 0.5 * IT + 400) + 2 * SO
    dn_annual = DN_ANNUAL + (1.5 * SO + PM + AA) + (2 * SO + 8 * AA)
    assert_cost(at, dn_setup, dn_annual)

    group = "downstream_sme"
    at.selectbox(key="company_group").set_value(group).run()
    at.number_input(key=f"_days:{group}:DS_S2:SO").set_value(2.5)
    at.number_input(key=f"suppliers:{group}").set_value(90)
    at.number_input(key=f"receipts:{group}").set_value(100).run()
    ds_setup = (DS_SETUP + 2 * (1.5 * SO + AA) + SO) * 0.9
    ds_annual = (DS_ANNUAL + 2 * (SO + 0.5 * AA) - 0.5 * (SO + 4 * AA)) * 0.9
    assert_cost(at, ds_setup, ds_annual)

    at.selectbox(key="company_group").set_value("operator_large_medium").run()
    assert_scenario(at, "Primary operator (small / micro)", "Small",
                    (PRIMARY_SETUP + 2 * SO) * 0.75, PRIMARY_ANNUAL * 0.75)
    assert_scenario(at, "Downstream (non-SME)", "Large", dn_setup, dn_annual)
    assert_scenario(at, "Downstream (SME)", "Medium", ds_setup, ds_annual)
    assert_report_matches_screen(at, downloads)

    at.selectbox(key="company_group").set_value("downstream_non_sme").run()
    assert at.number_input(key="suppliers:downstream_non_sme").value == 100
    assert at.number_input(key="receipts:downstream_non_sme").value == 800
    assert at.number_input(key="_days:downstream_non_sme:DN_S2:SO").value == 4
    assert_cost(at, dn_setup, dn_annual)
    assert_scenario(at, "Downstream (SME)", "Medium", ds_setup, ds_annual)


def test_blank_excluded_risk_tasks_do_not_block_low_risk_outputs(app):
    at, downloads = app
    group = "operator_large_medium"
    at.selectbox(key=f"risk:{group}").set_value("low")
    at.number_input(key=f"_days:{group}:OP_S6:SO").set_value(None)
    at.number_input(key=f"_days:{group}:OP_O5:SO").set_value(None).run()
    assert_cost(at, 54921.415636363636, 25238.484818181816)
    summary = {r["Item"]: r["Value"] for r in report_rows(downloads) if r["Section"] == "Summary"}
    assert summary["Status"] == "Complete"
    assert scenario(at, "Operator (large / medium)", "Large")["Status"] == "Calculated"
    assert scenario(at, "Operator (large / medium)", "Large", "Comparison 1")["Status"] == "TBC"
    assert_report_matches_screen(at, downloads)

    at.selectbox(key=f"risk:{group}").set_value("standard_high").run()
    assert metric(at, "Set-up cost") == "TBC"
    assert metric(at, "Annual cost") == "TBC"
    assert_report_matches_screen(at, downloads)
    at.number_input(key=f"_days:{group}:OP_S6:SO").set_value(0.0)
    at.number_input(key=f"_days:{group}:OP_O5:SO").set_value(0.0).run()
    assert_cost(at, OP_SETUP - 8 * SO, OP_ANNUAL - 6 * SO * 0.775)
    assert_report_matches_screen(at, downloads)


def test_raw_workload_entry_is_explained_beside_task_inputs(app):
    at, _ = app
    captions = " ".join(item.value for item in at.caption)
    assert "before batching, legality, volume or scenario adjustments" in captions
    # The workbook's D23 is effective 4.65 days; the raw app input remains 6.
    assert at.number_input(key="_days:operator_large_medium:OP_O5:SO").value == 6
    assert at.number_input(key="_days:operator_large_medium:OP_S_INFO:SO").value == 20


def test_cleared_controls_recover_after_reruns_without_an_exception(app):
    at, downloads = app
    # A rerun used to make required controls nullable, then None / 100 crashed.
    for key, restored_value in [
        ("legality:operator_large_medium", 50.0),
        ("year3_efficiency_percent", 10.0),
    ]:
        at.run()
        at.number_input(key=key).set_value(None).run()
        assert not at.exception
        if at.number_input(key=key).value is None:
            assert any("Enter a value" in item.value for item in at.info)
            assert not at.metric
        else:
            # Streamlit may retain a required numeric widget's valid default.
            assert at.number_input(key=key).value == restored_value
            assert_cost(at, OP_SETUP, OP_ANNUAL)
        at.number_input(key=key).set_value(restored_value).run()
        assert_cost(at, OP_SETUP, OP_ANNUAL)
        assert_report_matches_screen(at, downloads)

    # Required scalar controls must not change the deliberate pending-day input.
    at.number_input(key="_days:operator_large_medium:OP_S1:SO").set_value(None).run()
    assert not at.exception
    assert metric(at, "Set-up cost") == "TBC"
    assert metric(at, "Annual cost") == f"£{OP_ANNUAL:,.2f}"
