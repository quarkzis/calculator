# EUDR Phase 2 cost calculator

Streamlit calculator matching **EUDR Phase 2 - ASHE 2026 rates 09112026.xlsx**.
The model uses Adam's task estimates, the six Phase 2 corrections and the ASHE
2026 salaries. The workbook remains the reference; the app does not need Excel
or the original local workbook to run.

## Run the app

Use Python 3.10 or later:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run calculator.py
```

For Streamlit Community Cloud, keep `calculator.py`, `access_control.py`, `eudr_model.py`,
`data/phase2_inputs.json` and `requirements.txt` together in the repository.
Use `calculator.py` as the entry point.

## Shared-password access

The calculator requires a shared password before showing its inputs, results or
downloads. A missing or invalid password configuration blocks access.

Store only the password hash in Streamlit Community Cloud under **App settings →
Secrets**, or in `.streamlit/secrets.toml` for local use:

```toml
app_password_hash = "pbkdf2_sha256$600000$<salt>$<digest>"
```

Replace the example with a real hash. To generate one without putting a password
in your shell history, run this in an interactive Python session:

```python
from getpass import getpass
from access_control import hash_password
print(hash_password(getpass("New shared password: ")))
```

Share the password separately with the intended users. Never commit the password,
its hash configuration, or GitHub credentials. Both local credential files are
ignored by Git. The app has a Sign out button; signing out also clears that browser
session's calculation edits. Updating the configured hash requires users to log
in again on their next interaction. Five incorrect attempts trigger a short
cooldown in that browser session; this is not an account-wide rate limit.

This gate restricts the hosted calculator. The GitHub repository and any other
deployment have their own access settings; a public repository still exposes its
source code and packaged model inputs.

## Using the calculator

1. Select **Scenario 1–3** or **Defra 1–6**, using the same names as the Excel
   scenarios tab. The app opens on **Defra 4**, large operator, so its initial
   results correspond to `All_company_Scenarios (Phase 2)!D41:G41`.
   Choose a company group and permitted size; the displayed source cells update.
2. The selected scenario sets risk and operator DD, complexity and commodity
   factors. **Custom assumptions** restores the editable scenario controls.
   **Working-table base** is a separate option before Section 4 factors; it is
   not a predefined row in the scenarios tab. Set the applicable shared inputs.
   Operators have geolocation, DDS batching,
   local-laws, existing-DD, complexity and commodity controls. Primary operators
   have their own complexity and optional micro sensitivity. Downstream groups
   use supplier and receipt counts instead of the operator discounts.
3. Review the daily rates and edit task days as needed. A blank task estimate
   stays pending when the task is required; zero means no work. Low-risk cases
   exclude Article 10/11 tasks even if their estimates are pending.
   Enter days **before** batching, legality, volume or scenario adjustments.
   For example, annual Article 10 SO work starts at 6 days, not the 4.65 days
   displayed after the workbook's default legality factor. Article 9 uses the
   full information workload and a separate geolocation allocation.
   Switching company, size or visible task period keeps edits in this session.
4. Read setup, annual and year-3 costs, then download the CSV. Scenario 1 and 3
   show **N/A** for year 3; Scenario 2 uses 10%, while Defra uses its saved
   year-3 assumption. Working-table base also has no year-3 result. The combined
   total is **setup plus one annual cost**, not a three-year cumulative total.
   Detailed final costs and charts include the same factors as the totals.
5. Expand the scenario comparison to view the three comparison cases and six
   Defra cases with all saved edits across company groups, current rates and
   Phase 2 controls. Both downstream groups retain their own supplier/receipt
   counts and reference volumes. The two operator groups share task estimates,
   geolocation, batching and legality controls, as in the workbook.
   Small, Micro and Medium size factors are shared across applicable groups;
   Large remains fixed at 1. Primary complexity and the Micro/Small sensitivity
   remain active in the comparison when another group or size is selected.
   The same scenario definition drives the main result and comparison table.
   The main CSV records the selected scenario and corresponding Excel cells.
   Matching an edited workbook requires the same task days, rates and controls.

## Defaults and model rules

- Salaries: SO £46,262; LAW £50,856; PM £42,871; AA £29,425; IT £36,775.
  Day rates use salary × 1.22 / 220 with no intermediate rounding. The external
  consultant remains £800 per day. IT displays £203.93 using the specified
  salary, rather than the rounded £203.94 printed in Adam's note.
- Geolocation is an allocation within the Article 9 information workload.
  Increasing its share reduces the residual information task. With geolocation
  on, reallocating the share preserves the total. With it off, that share is
  excluded. The allocation cannot exceed the information workload for a role.
- Annual DDS work is 6 fixed days plus 6 variable days divided by consignments
  per DDS. At the default of 4, this is 7.5 days (£1,591.36).
- The local-laws factor is `1 - 0.5 * (1 - 0.55) = 0.775`. It applies to annual
  Article 10/11 risk work. The setup switch is **off** by default.
- Low-risk operators retain training, information and geolocation work, but
  exclude risk assessment and mitigation. The simplified primary group is
  available only for low-risk countries in this model.
- Primary small costs have size factor 1. Micro also defaults to 1 relative to
  small, with 0.75 available as a sensitivity. Primary complexity defaults to
  0.75; existing-DD and commodity factors do not apply.
- Downstream supplier controls affect setup/annual supplier tasks only (workbook
  rows 51/59 and 69/76). Receipt controls affect rows 60/77 only. Reference
  volumes are 50 suppliers/400 annual receipts for non-SME and 30/200 for SME.
  SME size factors are applied once: medium 0.9, small 0.75, micro 0.5.
- Scaling the entire downstream supplier setup task remains the workbook's
  provisional assumption. Extra annual geolocation IT/consultant days and the
  full-time salary sensitivity are not included.
- Defra defaults are DD 0.75 for setup and annual costs, operator complexity 1,
  primary complexity 0.75 and a 10% reduction from year 3. The comparison
  scenarios preserve their separate workbook factors and year-3 conventions.

At the delivered defaults, **Defra 4 / Large operator** costs **£59,086.48 setup,
£25,458.00 annually, £22,912.20 from year 3 and £84,544.47 setup plus one annual
cost**, matching cells D41:G41 in the Phase 2 scenarios tab.

The separate Working-table base remains **£78,781.97 setup and £33,944.00
annually**, before Section 4 factors. Batching and legality are already included
in that annual figure. These base amounts are in Working_table I17/I27, not in
the scenarios tab.

## Source and verification

`data/phase2_inputs.json` contains the task inputs and source workbook hash.
`eudr_model.py` owns all calculations; `calculator.py` supplies the interface and
reports. Inputs are packaged with the app so deployment does not depend on a
local Downloads or output directory.

`tests/fixtures/phase2_workbook.json` records independently evaluated workbook
outputs, including all 90 company/size/scenario combinations and controls for
geolocation, batching, legality and downstream volumes.

```sh
python -m pip install -r requirements-dev.txt
python -m pytest
```

The tests compare the calculation engine with those workbook fixtures and use
Streamlit AppTest to exercise input changes, pending estimates, switching groups
and CSV totals. Regression cases include custom size factors in comparisons,
excluded tasks with pending inputs, shared operator inputs, and simultaneous
edits across groups. Independent recalculation of the reference XLSX also checks
combinations of controls against the app without relying on saved fixtures.
