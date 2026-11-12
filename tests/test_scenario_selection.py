"""Named main-panel scenarios reconcile to the independently evaluated workbook."""

import json
from pathlib import Path

import pytest

from eudr_model import (
    SCENARIO_LABELS, Settings, apply_scenario, build_scenario_table,
    calculate, workbook_reference,
)


WORKBOOK = json.loads((Path(__file__).parent / 'fixtures/phase2_workbook.json').read_text(encoding='utf-8'))
FIELDS = {
    'setup': 'setup', 'ongoing': 'annual', 'ongoing_year3': 'annual_year3',
    'total_setup_plus_one_annual': 'total',
}


@pytest.mark.parametrize('case', WORKBOOK['scenario_cases'], ids=lambda case: case['id'])
def test_selected_profile_matches_all_four_excel_cells(case):
    # Deliberately different current custom choices must not leak into profiles.
    current = Settings(company=case['group'], size=case['size'].title(),
                       dd_setup=0.17, dd_annual=0.22, complexity=3, commodity=7)
    selected = apply_scenario(current, case['case_id'])
    result = calculate(selected)
    reference = workbook_reference(case['case_id'], current.company, current.size)
    assert reference['sheet'] == case['sheet']
    for expected_key, result_field in FIELDS.items():
        assert reference[result_field] == case['cells'][expected_key]
        expected = case['expected'][expected_key]
        actual = getattr(result, result_field)
        if expected == 'N/A':
            assert actual is None
        else:
            assert actual == pytest.approx(expected, rel=1e-12, abs=1e-7)


def test_names_match_the_excel_scenario_labels():
    assert list(SCENARIO_LABELS.values()) == [
        'Scenario 1', 'Scenario 2', 'Scenario 3',
        'Defra 1', 'Defra 2', 'Defra 3', 'Defra 4', 'Defra 5', 'Defra 6',
    ]


@pytest.mark.parametrize('prefix,company,size,risk', [
    ('operator_standard', 'operator_large_medium', 'Medium', 'standard_high'),
    ('operator_low', 'operator_large_medium', 'Large', 'low'),
    ('operator_small_micro_standard', 'operator_small_micro', 'Micro', 'standard_high'),
    ('operator_small_micro_low', 'operator_small_micro', 'Small', 'low'),
    ('primary', 'primary', 'Micro', 'low'),
    ('downstream_non_sme', 'downstream_non_sme', 'Large', 'standard_high'),
    ('downstream_sme', 'downstream_sme', 'Small', 'standard_high'),
])
def test_working_base_excludes_section_four_factors(prefix, company, size, risk):
    current = Settings(company=company, size=size, risk=risk, size_factor=0.6,
                       dd_setup=0.3, dd_annual=0.2, complexity=2, commodity=1.5,
                       primary_complexity=0.5, micro_ratio=0.75)
    selected = apply_scenario(current, 'working_base')
    result = calculate(selected)
    refs = workbook_reference('working_base', company, size, risk)
    for field, suffix in [('setup', '_setup'), ('annual', '_ongoing')]:
        expected = WORKBOOK['expected_working_totals'][prefix + suffix]
        assert getattr(result, field) == pytest.approx(expected['value'], abs=1e-7)
        assert refs[field] == expected['cell']
        assert refs['sheet'] == expected['sheet']
    assert result.annual_year3 is None
    assert refs['annual_year3'] is None
    assert refs['total'] is None
    assert selected.risk == risk


def test_profiles_preserve_shared_phase_two_inputs_and_defra_controls():
    current = Settings(
        company='operator_small_micro', size='Small', geolocation_enabled=False,
        batch_dds=8, legality_share=0.3, retained_legality_share=0.2,
        apply_legality_to_setup=True, primary_complexity=0.8, micro_ratio=0.6,
        size_factor=0.65, suppliers=70, receipts=500, reference_suppliers=55,
        reference_receipts=450, year3_efficiency=0.2,
        defra_dd_setup=0.5, defra_dd_annual=0.6, defra_complexity=1.25,
    )
    selected = apply_scenario(current, 'defra_4')
    for name in ('company', 'size', 'geolocation_enabled', 'batch_dds',
                 'legality_share', 'retained_legality_share', 'apply_legality_to_setup',
                 'primary_complexity', 'micro_ratio', 'size_factor', 'suppliers',
                 'receipts', 'reference_suppliers', 'reference_receipts'):
        assert getattr(selected, name) == getattr(current, name)
    assert (selected.dd_setup, selected.dd_annual, selected.complexity) == (0.5, 0.6, 1.25)
    assert selected.commodity == 1
    assert selected.year3_efficiency == 0.2
    assert apply_scenario(current, 'comparison_2').year3_efficiency == 0.1
    assert apply_scenario(current, 'comparison_1').year3_efficiency is None
    assert apply_scenario(current, 'comparison_3').year3_efficiency is None


def test_selected_profile_matches_comparison_after_shared_inputs_change():
    current = Settings(company='operator_small_micro', size='Small', batch_dds=8,
                       year3_efficiency=0.2, size_factor=0.6,
                       defra_dd_setup=0.5, defra_dd_annual=0.6, defra_complexity=1.25)
    table = build_scenario_table(settings=current, task_days={'OP_S1': {'SO': 31}})
    for scenario_id in SCENARIO_LABELS:
        result = calculate(apply_scenario(current, scenario_id), task_days={'OP_S1': {'SO': 31}})
        row = next(row for row in table if row['case_id'] == scenario_id and
                   row['company'] == current.company and row['Size'] == current.size)
        for field, column in [('setup', 'Setup (£)'), ('annual', 'Annual (£)'),
                              ('annual_year3', 'Annual year 3 (£)'), ('total', 'Setup + one annual (£)')]:
            assert getattr(result, field) == row[column]


def test_custom_has_no_false_excel_reference_and_primary_base_requires_low_risk():
    current = Settings(dd_setup=0.6, commodity=1.2, year3_efficiency=None)
    assert apply_scenario(current, 'custom') is current
    assert all(value is None for value in workbook_reference('custom', current.company, current.size).values())
    primary = apply_scenario(Settings(company='primary', size='Small'), 'working_base')
    assert not calculate(primary).eligible
    assert all(value is None for value in workbook_reference('working_base', 'primary', 'Small').values())


def test_invalid_profile_or_workbook_reference_is_rejected():
    with pytest.raises(ValueError, match='scenario'):
        apply_scenario(Settings(), 'not_a_case')
    with pytest.raises(ValueError, match='scenario'):
        workbook_reference('not_a_case', 'operator_large_medium', 'Large')
    with pytest.raises(ValueError, match='size'):
        workbook_reference('defra_4', 'primary', 'Large')
    with pytest.raises(ValueError, match='risk'):
        workbook_reference('working_base', 'operator_large_medium', 'Large', 'unknown')
