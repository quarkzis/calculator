"""Streamlit interface for the Phase 2 EUDR cost model."""

import csv
from dataclasses import asdict, replace
from datetime import date
from io import StringIO
import re

import pandas as pd
import plotly.express as px
import streamlit as st

from access_control import require_access
from eudr_model import (
    COMPANY_GROUPS, COMPANY_SIZES, DEFAULT_DAY_RATES, ROLES, ROLE_LABELS,
    SCENARIO_LABELS, Settings, apply_scenario, build_scenario_table, calculate,
    get_tasks, workbook_reference,
)


st.set_page_config(page_title="EUDR Due Diligence Costs Calculator", page_icon="💼", layout="wide")
require_access()

PHASE_LABELS = {"setup": "Set-up", "ongoing": "Annual"}
SIZE_FACTORS = {"Large": 1.0, "Medium": 0.9, "Small": 0.75, "Micro": 0.5}
DD_OPTIONS = {
    "No existing due diligence": (1.0, 1.0),
    "Partial existing due diligence": (0.75, 0.75),
    "Full existing due diligence": (0.5, 1.0),
}
COMPLEXITY_OPTIONS = {"Simple": 0.75, "Standard": 1.0, "Complex": 2.0}
RISK_LABELS = {"standard_high": "Standard / high risk", "low": "Low risk"}
SCENARIO_OPTIONS = {
    "defra_4": "Defra 4 — standard/high risk, commodity factor 1",
    "comparison_1": "Scenario 1 — high risk, complex supply chain, 8 commodities",
    "comparison_2": "Scenario 2 — low risk, simple supply chain, 1 commodity",
    "comparison_3": "Scenario 3 — standard risk, standard supply chain, 4 commodities",
    "defra_1": "Defra 1 — low risk, commodity factor 1",
    "defra_2": "Defra 2 — low risk, commodity factor 1.5",
    "defra_3": "Defra 3 — low risk, commodity factor 2",
    "defra_5": "Defra 5 — standard/high risk, commodity factor 1.5",
    "defra_6": "Defra 6 — standard/high risk, commodity factor 2",
    "working_base": "Working-table base — before Section 4 scenario factors",
    "custom": "Custom assumptions",
}
DISPLAY_SCENARIOS = {**SCENARIO_LABELS, "working_base": "Working-table base", "custom": "Custom assumptions"}
DETAIL_COLUMNS = {
    "code": "Task code", "task": "Task", "phase": "Period", "role": "Role",
    "input_days": "Input days", "effective_days": "Effective days", "day_rate": "Day rate (£)",
    "base_cost": "Cost before scenario factors (£)", "task_factor": "Task factor",
    "scenario_factor": "Scenario factor", "final_cost": "Final cost (£)",
}


def money(value, *, eligible=True):
    if not eligible:
        return "N/A"
    return "TBC" if value is None or pd.isna(value) else f"£{value:,.2f}"


def remember_control(widget_key, saved_key):
    st.session_state["model_controls"][saved_key] = st.session_state[widget_key]


def persistent_control(widget, *args, key, shared_key=None, **kwargs):
    """Store model inputs separately from widgets that Streamlit may remove."""
    saved = st.session_state.setdefault("model_controls", {})
    saved_key = shared_key or key
    if saved_key in saved:
        if key not in st.session_state or st.session_state[key] != saved[saved_key]:
            st.session_state[key] = saved[saved_key]
        if widget == st.selectbox:
            kwargs["index"] = None
        elif widget == st.checkbox:
            kwargs.pop("value", None)
    value = widget(*args, key=key, on_change=remember_control,
                   args=(key, saved_key), **kwargs)
    saved[saved_key] = value
    if widget == st.number_input and value is None:
        st.info(f"Enter a value for {args[0]} to continue.")
        st.stop()
    return value


def shared_controls():
    """The workbook's shared controls remain active when their widgets are hidden."""
    saved = st.session_state.setdefault("model_controls", {})
    legality = saved.get("operator:legality", 50.0)
    retained = saved.get("operator:retained", 55.0)
    return {
        "geolocation_enabled": saved.get("operator:geo", True),
        "batch_dds": saved.get("operator:batch", 4.0),
        "legality_share": None if legality is None else legality / 100.0,
        "retained_legality_share": None if retained is None else retained / 100.0,
        "apply_legality_to_setup": saved.get("operator:setup_legality", False),
        "primary_complexity": saved.get("primary_complexity", 0.75),
        "micro_ratio": saved.get("primary_micro_ratio", 1.0),
    }


def task_family(company):
    return "operator" if company.startswith("operator_") else company


def remember_task_day(company, code, role, widget_key):
    """Keep edits after widgets for a hidden company or period are removed."""
    st.session_state["task_inputs"][task_family(company)][code][role] = st.session_state[widget_key]


def get_company_task_inputs(company, tasks):
    st.session_state.setdefault("task_inputs", {})
    families = st.session_state["task_inputs"]
    saved = families.setdefault(task_family(company), families.get(company, {}))
    for task in tasks:
        values = saved.setdefault(task.code, {})
        for role in ROLES:
            values.setdefault(role, task.days.get(role, 0.0))
    return saved


def render_task_inputs(company, tasks, period):
    saved = get_company_task_inputs(company, tasks)
    phases = ("setup", "ongoing") if period == "Both periods" else (
        "setup" if period == "Set-up only" else "ongoing",
    )
    for phase in phases:
        with st.expander(f"{PHASE_LABELS[phase]} task days", expanded=True):
            for task in tasks:
                if task.phase != phase:
                    continue
                st.markdown(f"**{task.name}**")
                mechanism = str(task.mechanism).lower()
                if mechanism == "information_pool":
                    st.caption("Total Article 9 information work before separating geolocation. The allocation below is taken out of this total.")
                elif mechanism == "geolocation":
                    st.caption("Geolocation share of the Article 9 information work above. It is included once when the geolocation switch is on.")
                elif company.startswith("operator_") and "dds" in (mechanism + task.code.lower()):
                    if "fixed" in (mechanism + task.code.lower()):
                        st.caption("Fixed annual DDS effort: this part is not divided by consignments per DDS.")
                    elif "variable" in mechanism or "batch" in mechanism:
                        st.caption("Variable annual DDS effort: the batching control divides this part only.")
                columns = st.columns(len(ROLES))
                for column, role in zip(columns, ROLES):
                    widget_key = f"_days:{company}:{task.code}:{role}"
                    value = saved[task.code][role]
                    st.session_state[widget_key] = None if value is None else float(value)
                    with column:
                        st.number_input(
                            f"{role} days", min_value=0.0, value=None, step=0.25, format="%.2f",
                            key=widget_key, help=ROLE_LABELS[role], on_change=remember_task_day,
                            args=(company, task.code, role, widget_key),
                        )
    return {task.code: dict(saved[task.code]) for task in tasks}


def strict_sum(values):
    """Keep an unresolved task or role subtotal unresolved."""
    return None if values.isna().any() else float(values.sum())


def readable_missing(text, tasks):
    text = str(text)
    for task in sorted(tasks, key=lambda item: len(item.code), reverse=True):
        text = re.sub(rf"\b{re.escape(task.code)}\b", task.name, text)
    return text


def create_report_csv(settings, result, rates, scenario_id, reference):
    """Export summary and cost detail with the same final costs as the screen."""
    output = StringIO()
    columns = [
        "Section", "Item", "Period", "Role", "Input days", "Effective days",
        "Day rate GBP", "Cost before scenario factors GBP", "Task factor",
        "Scenario factor", "Final cost GBP", "Value",
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()

    def write(section, item, value=None, **other):
        writer.writerow({"Section": section, "Item": item, "Value": value, **other})

    write("Summary", "Calculation date", date.today().isoformat())
    write("Summary", "Scenario", DISPLAY_SCENARIOS[scenario_id])
    write("Summary", "Excel sheet", reference["sheet"] or "No predefined workbook scenario")
    for label, field in (("set-up", "setup"), ("annual", "annual"),
                         ("year-3", "annual_year3"), ("combined-total", "total")):
        write("Summary", f"Excel {label} cell", reference[field] or "N/A")
    write("Summary", "Company group", COMPANY_GROUPS[settings.company])
    write("Summary", "Business size", settings.size)
    write("Summary", "Status", "N/A" if not result.eligible else ("TBC" if result.missing_inputs else "Complete"))
    if not result.eligible:
        write("Summary", "Reason", result.reason)
    for label, value in [
        ("Set-up cost GBP", result.setup), ("Annual cost GBP", result.annual),
        ("Annual cost from year 3 GBP", result.annual_year3),
        ("Set-up plus one annual cost GBP", result.total),
    ]:
        applicable = result.eligible and not (
            label == "Annual cost from year 3 GBP" and settings.year3_efficiency is None
        )
        write("Summary", label, value if value is not None else ("TBC" if applicable else "N/A"))
    for name, value in asdict(settings).items():
        write("Settings", name, "" if value is None else value)
    for role in ROLES:
        write("Day rates", ROLE_LABELS[role], rates[role], Role=role)
    for factor in result.factors:
        for phase, key in [("Set-up", "setup"), ("Annual", "annual")]:
            write("Applied factors", factor["factor"], factor.get(key), Period=phase)
    for entry in result.details:
        write(
            "Cost detail", f"{entry['code']}: {entry['task']}",
            Period=PHASE_LABELS.get(entry["phase"], entry["phase"]), Role=entry["role"],
            **{
                "Input days": entry.get("input_days"), "Effective days": entry.get("effective_days"),
                "Day rate GBP": entry.get("day_rate"), "Cost before scenario factors GBP": entry.get("base_cost"),
                "Task factor": entry.get("task_factor"), "Scenario factor": entry.get("scenario_factor"),
                "Final cost GBP": entry.get("final_cost"),
            },
        )
    for item in result.missing_inputs:
        write("Missing inputs", str(item), "TBC")
    return output.getvalue()


st.title("EUDR Due Diligence Costs Calculator")
st.caption("Phase 2 · Enter task days and daily rates to calculate company costs.")
st.caption("Edits are kept while you switch company groups in this session. Size factors are shared by size; the two operator groups also share task days and Phase 2 controls.")
st.header("Scenario")
scenario_id = persistent_control(st.selectbox, "Excel scenario", options=list(SCENARIO_OPTIONS),
    format_func=SCENARIO_OPTIONS.get, key="scenario_id")
is_named_scenario = scenario_id in SCENARIO_LABELS
is_working_base = scenario_id == "working_base"
if is_working_base:
    st.info("This is the Working_table base, not a row in All_company_Scenarios. Phase 2 controls such as batching and legality still apply; Section 4 scenario factors do not. The workbook does not define a year-3 figure for this base.")
elif scenario_id == "custom":
    st.caption("Choose your own risk and scenario factors. These results do not identify a predefined row in the workbook.")
else:
    st.caption("The selected workbook scenario sets country risk, operator DD, complexity, commodity factors and year-3 treatment. Shared task days, rates and Phase 2 controls remain editable. Choose Custom assumptions to use different scenario factors.")
with st.expander("Defra assumptions and year 3"):
    st.caption("The DD and complexity factors below apply to Defra 1–6. The year-3 reduction applies to Defra and Custom assumptions. Scenario 2 uses 10%; Scenarios 1 and 3 show N/A for year 3.")
    defra_columns = st.columns(3)
    with defra_columns[0]:
        defra_dd_setup = persistent_control(st.number_input,
            "Defra existing-DD factor: set-up", min_value=0.0, value=0.75,
            step=0.05, format="%.2f", key="defra_dd_setup")
    with defra_columns[1]:
        defra_dd_annual = persistent_control(st.number_input,
            "Defra existing-DD factor: annual", min_value=0.0, value=0.75,
            step=0.05, format="%.2f", key="defra_dd_annual")
    with defra_columns[2]:
        defra_complexity = persistent_control(st.number_input,
            "Defra operator complexity factor", min_value=0.0, value=1.0,
            step=0.05, format="%.2f", key="defra_complexity")
    shared_year3_efficiency = persistent_control(st.number_input,
        "Annual efficiency reduction from year 3 (%)", min_value=0.0,
        max_value=100.0, value=10.0, step=1.0, key="year3_efficiency_percent",
        help="Used by Defra and Custom assumptions. A 10% reduction retains 90% of annual cost.",
    ) / 100.0
st.header("Company and assumptions")
company = persistent_control(st.selectbox,
    "Company group", options=list(COMPANY_GROUPS),
    format_func=lambda key: COMPANY_GROUPS[key], key="company_group",
)
is_operator = company.startswith("operator_")
is_primary = company == "primary"
is_downstream = company.startswith("downstream_")
company_columns = st.columns(2)
with company_columns[0]:
    size = persistent_control(st.selectbox, "Business size", options=COMPANY_SIZES[company], key=f"size:{company}")
with company_columns[1]:
    if is_named_scenario:
        risk = apply_scenario(Settings(), scenario_id).risk
        st.write(f"Source-country risk: **{RISK_LABELS[risk]}**")
        st.caption(f"Set by {DISPLAY_SCENARIOS[scenario_id]}.")
    elif is_operator or is_primary:
        risk_options = ["low", "standard_high"] if is_primary else ["standard_high", "low"]
        risk = persistent_control(st.selectbox,
            "Source-country risk", options=risk_options,
            format_func=lambda key: RISK_LABELS[key], key=f"risk:{company}",
        )
    else:
        risk = "standard_high"

settings_values = {**shared_controls(), "company": company, "size": size, "risk": risk}
settings_values.update(defra_dd_setup=defra_dd_setup, defra_dd_annual=defra_dd_annual,
                       defra_complexity=defra_complexity, year3_efficiency=shared_year3_efficiency)
if not is_working_base and not is_primary and company != "downstream_non_sme":
    settings_values["size_factor"] = persistent_control(st.number_input,
        "Business size factor", min_value=0.0, value=SIZE_FACTORS[size],
        step=0.05, format="%.2f", key=f"size_factor:{company}:{size}", shared_key=f"size_factor:{size}",
        disabled=size == "Large",
        help="Shared by all groups using this business size. Applied once. Large is fixed at 1, as in the workbook.",
    )

if is_operator:
    left, right = st.columns(2)
    with left:
        settings_values["geolocation_enabled"] = persistent_control(st.checkbox,
            "Include geolocation costs", value=True, key=f"geo:{company}", shared_key="operator:geo",
        )
        settings_values["batch_dds"] = persistent_control(st.number_input,
            "Average consignments per DDS", min_value=1.0, value=4.0,
            step=1.0, format="%.2f", key=f"batch:{company}", shared_key="operator:batch",
            help="Only variable annual DDS work is divided by this number. Fixed work remains.",
        )
        legality = persistent_control(st.number_input,
            "Legality share of risk-assessment effort (%)", min_value=0.0,
            max_value=100.0, value=50.0, step=1.0, key=f"legality:{company}", shared_key="operator:legality",
        )
        retained = persistent_control(st.number_input,
            "Legality effort retained for land-use checks (%)", min_value=0.0,
            max_value=100.0, value=55.0, step=1.0, key=f"retained:{company}", shared_key="operator:retained",
        )
        settings_values["legality_share"] = legality / 100.0
        settings_values["retained_legality_share"] = retained / 100.0
        settings_values["apply_legality_to_setup"] = persistent_control(st.checkbox,
            "Apply the legality reduction to set-up work", value=False, key=f"setup_legality:{company}", shared_key="operator:setup_legality",
        )
        retained_total = 1 - (legality / 100) * (1 - retained / 100)
        st.caption(f"Combined Article 10 and 11 effort retained: {retained_total:.1%}. Low-risk cases exclude these tasks.")
    with right:
        if scenario_id == "custom":
            dd = persistent_control(st.selectbox, "Existing due diligence", list(DD_OPTIONS), key=f"dd:{company}")
            settings_values["dd_setup"] = persistent_control(st.number_input,
                "Existing-DD factor: set-up", min_value=0.0, value=DD_OPTIONS[dd][0],
                step=0.05, format="%.2f", key=f"dd_setup:{company}:{dd}",
            )
            settings_values["dd_annual"] = persistent_control(st.number_input,
                "Existing-DD factor: annual", min_value=0.0, value=DD_OPTIONS[dd][1],
                step=0.05, format="%.2f", key=f"dd_annual:{company}:{dd}",
            )
            complexity = persistent_control(st.selectbox,
                "Supply-chain complexity", list(COMPLEXITY_OPTIONS), index=1, key=f"complexity_choice:{company}",
            )
            settings_values["complexity"] = persistent_control(st.number_input,
                "Supply-chain complexity factor", min_value=0.0, value=COMPLEXITY_OPTIONS[complexity],
                step=0.05, format="%.2f", key=f"complexity_factor:{company}:{complexity}",
            )
            commodity_choice = persistent_control(st.selectbox,
                "Commodity cost multiplier", [1.0, 1.5, 2.0],
                format_func=lambda value: f"{value:g} × base cost", key=f"commodity_choice:{company}",
            )
            settings_values["commodity"] = persistent_control(st.number_input,
                "Commodity factor", min_value=0.0, value=commodity_choice,
                step=0.1, format="%.2f", key=f"commodity_factor:{company}:{commodity_choice}",
            )
        else:
            active_factors = apply_scenario(Settings(**settings_values), scenario_id)
            st.write(f"**{DISPLAY_SCENARIOS[scenario_id]} operator factors**")
            st.write(f"Existing DD: {active_factors.dd_setup:g} set-up / {active_factors.dd_annual:g} annual")
            st.write(f"Supply-chain complexity: {active_factors.complexity:g}")
            st.write(f"Commodity factor: {active_factors.commodity:g}")

elif is_primary and not is_working_base:
    primary_columns = st.columns(2)
    with primary_columns[0]:
        settings_values["primary_complexity"] = persistent_control(st.number_input,
            "Primary-producer complexity factor", min_value=0.0, value=0.75,
            step=0.05, format="%.2f", key="primary_complexity",
        )
    with primary_columns[1]:
        if size == "Micro":
            settings_values["micro_ratio"] = persistent_control(st.number_input,
                "Micro cost relative to small", min_value=0.0, max_value=1.0, value=1.0,
                step=0.05, format="%.2f", key="primary_micro_ratio",
                help="1 uses the same task estimate. 0.75 is the optional sensitivity for a micro producer.",
            )
    st.caption("The task days describe a small producer. No additional small-business size factor is applied.")

elif is_downstream:
    reference_suppliers, reference_receipts = ((50, 400) if company == "downstream_non_sme" else (30, 200))
    volume_columns = st.columns(2)
    with volume_columns[0]:
        settings_values["suppliers"] = persistent_control(st.number_input,
            "Number of suppliers", min_value=0, value=reference_suppliers,
            step=1, key=f"suppliers:{company}",
        )
    with volume_columns[1]:
        settings_values["receipts"] = persistent_control(st.number_input,
            "Receipts per year", min_value=0, value=reference_receipts,
            step=1, key=f"receipts:{company}",
        )
    with st.expander("Reference business for the task estimates"):
        st.caption("Task days are estimated at these reference volumes. Supplier-record tasks scale with suppliers; reference-number capture scales with receipts.")
        reference_columns = st.columns(2)
        with reference_columns[0]:
            settings_values["reference_suppliers"] = persistent_control(st.number_input,
                "Reference suppliers", min_value=1, value=reference_suppliers,
                step=1, key=f"reference_suppliers:{company}",
            )
        with reference_columns[1]:
            settings_values["reference_receipts"] = persistent_control(st.number_input,
                "Reference receipts per year", min_value=1, value=reference_receipts,
                step=1, key=f"reference_receipts:{company}",
            )
    st.caption("Other downstream tasks remain fixed. Existing-DD and commodity multipliers are 1.")

st.header("Daily rates")
st.caption("Defaults use ASHE 2026 annual pay for all employees × 1.22 / 220 working days, plus an £800 external-consultant day rate. Rates display two decimals; calculations retain full precision.")
rate_columns = st.columns(3)
day_rates = {}
for index, role in enumerate(ROLES):
    with rate_columns[index % 3]:
        day_rates[role] = persistent_control(st.number_input,
            f"{ROLE_LABELS[role]} (£/day)", min_value=0.0,
            value=float(DEFAULT_DAY_RATES[role]), step=0.01, format="%.2f", key=f"rate:{role}",
        )

st.header("Task days")
st.caption("Enter person-days before batching, legality, volume or scenario adjustments. Set-up is one-off; annual is one year's effort. Enter 0 for no work, or clear a value to leave an estimate pending.")
if is_operator:
    with st.expander("Which Excel days should I enter?"):
        st.write("Use the original workload, before the Excel formulas apply adjustments. For example, enter 6 SO days for annual Article 10 work, not the 4.65 days after the default legality adjustment. For Article 9 set-up, enter the full 20 SO days and allocate 10 to geolocation below; do not enter the residual 10 as the full workload.")
        st.write("Enter fixed and variable DDS days separately. The app divides only the variable days by consignments per DDS. The cost breakdown shows both input days and effective days so you can check each adjustment.")
        if risk == "low":
            st.write("Risk assessment and mitigation tasks are excluded for a low-risk country. Their estimates are retained for standard/high-risk cases; leaving them pending does not block this low-risk calculation.")
period = st.radio("Show task period", ["Both periods", "Set-up only", "Annual only"], horizontal=True, key="task_period")
tasks = get_tasks(company)
task_days = render_task_inputs(company, tasks, period)

try:
    model_inputs = Settings(**settings_values)
    settings = apply_scenario(model_inputs, scenario_id)
    reference = workbook_reference(scenario_id, company, size, settings.risk)
    result = calculate(settings, day_rates=day_rates, task_days=task_days)
except ValueError as error:
    st.error(str(error))
    st.stop()

st.header("Cost results")
st.write(f"**Active scenario: {DISPLAY_SCENARIOS[scenario_id]} · {COMPANY_GROUPS[company]} · {size}**")
if reference["sheet"]:
    source_labels = [("Set-up", "setup"), ("Annual", "annual"), ("Year 3", "annual_year3"), ("Combined total", "total")]
    source_cells = "; ".join(f"{label}: {reference[field]}" for label, field in source_labels if reference[field])
    st.caption(f"Excel — {reference['sheet']}: {source_cells}")
    st.caption("These are the corresponding Excel formula cells. Compare using the same task days, rates and shared assumptions; edited inputs change the result.")
elif scenario_id == "custom":
    st.caption("Custom assumptions have no single predefined scenario row in Excel.")
else:
    st.caption("There is no applicable Working_table base for this company and risk selection.")
if settings.year3_efficiency is None:
    st.caption("Annual cost from year 3 is N/A for this selection, as in the workbook.")
if not result.eligible:
    st.info(result.reason)
    if is_primary and is_named_scenario:
        st.info("For the simplified primary-operator case, select Scenario 2 or Defra 1, 2 or 3 (low risk).")
elif result.missing_inputs:
    st.info("Some required task estimates are still pending. Complete them, or enter 0 where no work is required, to calculate the affected totals.")
    with st.expander("Inputs still to complete"):
        for item in result.missing_inputs:
            st.write(readable_missing(item, tasks))

metrics = st.columns(4)
for column, label, value in zip(
    metrics,
    ["Set-up cost", "Annual cost", "Annual cost from year 3", "Set-up + one annual cost"],
    [result.setup, result.annual, result.annual_year3, result.total],
):
    applicable = result.eligible and not (label == "Annual cost from year 3" and settings.year3_efficiency is None)
    column.metric(label, money(value, eligible=applicable))
st.caption("The combined total includes set-up and one annual cost. It is not a three-year total.")

with st.expander("Costs before scenario factors and applied factors"):
    base_columns = st.columns(2)
    base_columns[0].metric("Set-up before scenario factors", money(result.base_setup, eligible=result.eligible))
    base_columns[1].metric("Annual before scenario factors", money(result.base_annual, eligible=result.eligible))
    if is_operator:
        st.write(f"Geolocation allocation: {money(result.geo_setup)} set-up and {money(result.geo_annual)} per year.")
    if result.factors:
        st.dataframe(pd.DataFrame(result.factors).rename(columns={"factor": "Factor", "setup": "Set-up", "annual": "Annual"}), use_container_width=True, hide_index=True)

detail_df = pd.DataFrame(result.details, columns=list(DETAIL_COLUMNS))
shown_phases = ["setup", "ongoing"] if period == "Both periods" else ["setup" if period == "Set-up only" else "ongoing"]
shown_details = detail_df.loc[detail_df["phase"].isin(shown_phases)].copy()
st.subheader(f"Cost breakdown: {period.lower()}")
if result.eligible and not shown_details.empty:
    display_details = shown_details.copy()
    display_details["phase"] = display_details["phase"].map(PHASE_LABELS)
    st.dataframe(display_details.rename(columns=DETAIL_COLUMNS), use_container_width=True, hide_index=True)
    task_summary = shown_details.groupby(["phase", "code", "task"], sort=False, as_index=False)["final_cost"].agg(strict_sum)
    task_summary["phase"] = task_summary["phase"].map(PHASE_LABELS)
    st.dataframe(task_summary.rename(columns={"phase": "Period", "code": "Task code", "task": "Task", "final_cost": "Final cost (£)"}), use_container_width=True, hide_index=True)
    complete_periods = {"setup": result.setup is not None, "ongoing": result.annual is not None}
    if all(complete_periods[phase] for phase in shown_phases):
        positive = shown_details.loc[shown_details["final_cost"].fillna(0) > 0]
        if not positive.empty:
            role_summary = positive.groupby("role", as_index=False)["final_cost"].sum()
            charts = st.columns(2)
            with charts[0]:
                fig = px.pie(role_summary, names="role", values="final_cost", title="Final cost by role")
                st.plotly_chart(fig, use_container_width=True)
            with charts[1]:
                fig = px.bar(
                    task_summary, x="code", y="final_cost", color="phase", hover_data=["task"],
                    title="Final cost by task", labels={"code": "Task", "final_cost": "Final cost (£)", "phase": "Period"},
                    color_discrete_map={"Set-up": "#1f77b4", "Annual": "#ff7f0e"},
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("The selected period has zero cost.")

st.header("Download results")
csv_report = create_report_csv(settings, result, day_rates, scenario_id, reference)
st.download_button(
    "Download CSV report", data=csv_report.encode("utf-8-sig"),
    file_name=f"eudr_phase2_{scenario_id}_{company}_{date.today():%Y%m%d}.csv", mime="text/csv", key="download_current",
)

with st.expander("Compare the three scenarios and Defra cases"):
    st.caption("These are the workbook's three comparison scenarios and six Defra cases. All saved task edits, size factors, Phase 2 controls, daily rates and both downstream groups' volumes are included. The two operator groups share task days and Phase 2 controls.")
    st.caption("The three comparison scenarios retain their own existing-DD, complexity and commodity assumptions. The second includes a 10% year-3 reduction. The Defra cases use the shared assumptions at the top of this page.")
    comparison_settings = model_inputs
    all_task_days = {}
    for group in COMPANY_GROUPS:
        all_task_days.update(get_company_task_inputs(group, get_tasks(group)))
    saved_controls = st.session_state["model_controls"]
    company_settings = {
        group: Settings(
            company=group, size=COMPANY_SIZES[group][0],
            **{name: saved_controls.get(f"{name}:{group}") for name in
               ("suppliers", "receipts", "reference_suppliers", "reference_receipts")},
        )
        for group in ("downstream_non_sme", "downstream_sme")
    }
    shared_sizes = {
        size: saved_controls.get(f"size_factor:{size}", default)
        for size, default in SIZE_FACTORS.items()
    }
    try:
        scenarios = pd.DataFrame(build_scenario_table(
            day_rates=day_rates, task_days=all_task_days, settings=comparison_settings,
            company_settings=company_settings, size_factors=shared_sizes,
        ))
        scenario_output = scenarios.drop(columns=["case_id", "company"], errors="ignore")
        scenario_output["Scenario"] = scenarios["case_id"].map(SCENARIO_LABELS)
        scenario_output["Excel cells"] = [
            f"{ref['setup']}:{ref['total']}" for ref in (
                workbook_reference(row["case_id"], row["company"], row["Size"])
                for row in scenarios.to_dict("records")
            )
        ]
        st.dataframe(
            scenario_output, use_container_width=True, hide_index=True,
            column_config={
                column: st.column_config.NumberColumn(column, format="%.2f")
                for column in scenario_output.columns if "(£)" in column
            },
        )
        st.download_button(
            "Download scenario comparison CSV", data=scenario_output.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"eudr_phase2_scenarios_{date.today():%Y%m%d}.csv", mime="text/csv", key="download_scenarios",
        )
    except ValueError as error:
        st.info(str(error))
