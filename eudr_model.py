"""Phase 2 calculation engine, independent of Streamlit.

Inputs and comparison definitions are transcribed from the verified 9 November
ASHE 2026 workbook. Money is never rounded during calculation. Results use None
for incomplete/inapplicable costs, distinct from a legitimate zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping
import json
import math

_INPUTS = json.loads((Path(__file__).parent / 'data/phase2_inputs.json').read_text(encoding='utf-8'))
ROLES = ('SO', 'LAW', 'PM', 'AA', 'IT', 'EC')
ROLE_LABELS = {
    'SO': 'Sustainability Officer', 'LAW': 'Lawyer',
    'PM': 'Procurement / Technical Manager', 'AA': 'Administrative Assistant',
    'IT': 'IT Professional', 'EC': 'External Consultant',
}
ANNUAL_SALARIES = dict(_INPUTS['annual_salaries'])
DEFAULT_DAY_RATES = {role: salary * 1.22 / 220 for role, salary in ANNUAL_SALARIES.items()}
DEFAULT_DAY_RATES['EC'] = 800.0
COMPANY_GROUPS = {
    'operator_large_medium': 'Operator (large / medium)',
    'operator_small_micro': 'Operator (small / micro)',
    'primary': 'Primary operator (small / micro)',
    'downstream_non_sme': 'Downstream (non-SME)',
    'downstream_sme': 'Downstream (SME)',
}
COMPANY_SIZES = {
    'operator_large_medium': ('Large', 'Medium'),
    'operator_small_micro': ('Small', 'Micro'),
    'primary': ('Small', 'Micro'),
    'downstream_non_sme': ('Large',),
    'downstream_sme': ('Medium', 'Small', 'Micro'),
}
SIZE_FACTORS = {'Large': 1.0, 'Medium': 0.9, 'Small': 0.75, 'Micro': 0.5}
REFERENCE_VOLUMES = {'downstream_non_sme': (50, 400), 'downstream_sme': (30, 200)}


@dataclass(frozen=True)
class Task:
    code: str
    name: str
    phase: str
    days: dict[str, float]
    mechanism: str
    excel_row: int


@dataclass(frozen=True)
class Settings:
    company: str = 'operator_large_medium'
    size: str = 'Large'
    risk: str = 'standard_high'
    geolocation_enabled: bool = True
    batch_dds: float = 4.0
    legality_share: float = 0.5
    retained_legality_share: float = 0.55
    apply_legality_to_setup: bool = False
    primary_complexity: float = 0.75
    micro_ratio: float = 1.0
    suppliers: float | None = None
    receipts: float | None = None
    reference_suppliers: float | None = None
    reference_receipts: float | None = None
    dd_setup: float = 1.0
    dd_annual: float = 1.0
    complexity: float = 1.0
    commodity: float = 1.0
    size_factor: float | None = None
    year3_efficiency: float | None = 0.1
    defra_dd_setup: float = 0.75
    defra_dd_annual: float = 0.75
    defra_complexity: float = 1.0


@dataclass
class Result:
    eligible: bool = True
    reason: str = ''
    base_setup: float | None = None
    base_annual: float | None = None
    setup: float | None = None
    annual: float | None = None
    annual_year3: float | None = None
    total: float | None = None
    geo_setup: float | None = 0.0
    geo_annual: float | None = 0.0
    details: list[dict] = field(default_factory=list)
    factors: list[dict] = field(default_factory=list)
    missing_inputs: tuple[str, ...] = ()


def get_tasks(company: str) -> tuple[Task, ...]:
    if company not in COMPANY_GROUPS:
        raise ValueError('Select a valid company group.')
    family = 'operator' if company.startswith('operator_') else company
    return tuple(Task(**{**t, 'days': dict(t['days'])}) for t in _INPUTS['tasks'][family])


def _number(value, label, minimum=0.0, maximum=None, whole=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number.')
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f'{minimum:g} or more' if maximum is None else f'between {minimum:g} and {maximum:g}'
        raise ValueError(f'{label} must be {bounds}.')
    if whole and value != int(value):
        raise ValueError(f'{label} must be a whole number.')
    return float(value)


def _complete_sum(values):
    values = list(values)
    return None if any(x is None for x in values) else sum(values)


def _settings_factors(settings):
    s = settings
    if s.company not in COMPANY_GROUPS or s.size not in COMPANY_SIZES[s.company]:
        raise ValueError('Select a valid company group and business size.')
    if s.risk not in ('low', 'standard_high'):
        raise ValueError('Country risk must be low or standard/high.')
    if s.year3_efficiency is not None:
        _number(s.year3_efficiency, 'Year-3 efficiency reduction', 0, 1)
    factors = []
    size = 1.0
    if s.company == 'primary':
        _number(s.primary_complexity, 'Primary complexity')
        _number(s.micro_ratio, 'Primary micro / small ratio', 0, 1)
        size = s.micro_ratio if s.size == 'Micro' else 1.0
        setup = annual = s.primary_complexity * size
        factors.extend([{'factor': 'Primary complexity', 'setup': s.primary_complexity, 'annual': s.primary_complexity}, {'factor': 'Primary size ratio', 'setup': size, 'annual': size}])
    else:
        if s.company != 'downstream_non_sme':
            size = SIZE_FACTORS[s.size] if s.size_factor is None else _number(s.size_factor, 'Business size factor')
        setup = annual = size
        if s.company.startswith('operator_'):
            for attr in ['dd_setup', 'dd_annual', 'complexity', 'commodity']:
                _number(getattr(s, attr), attr.replace('_', ' ').title())
            setup *= s.dd_setup * s.complexity * s.commodity
            annual *= s.dd_annual * s.complexity * s.commodity
            factors.extend([
                {'factor': 'Existing due diligence', 'setup': s.dd_setup, 'annual': s.dd_annual},
                {'factor': 'Supply-chain complexity', 'setup': s.complexity, 'annual': s.complexity},
                {'factor': 'Commodities', 'setup': s.commodity, 'annual': s.commodity},
            ])
        factors.append({'factor': 'Business size', 'setup': size, 'annual': size})
    return {'setup': setup, 'ongoing': annual}, factors


def calculate(settings: Settings, day_rates: Mapping | None = None, task_days: Mapping | None = None) -> Result:
    """Calculate one company. Task controls precede the group's scenario factors.

    A task override can contain only the edited roles. Explicit None means the
    estimate is pending. Geolocation allocations are subtracted from the Article
    9 pool before the optional geolocation component is included.
    """
    s = settings
    scenario_factors, factors = _settings_factors(s)
    if s.company == 'primary' and s.risk != 'low':
        return Result(eligible=False, reason='The simplified primary-operator case is available only for a low-risk country in this model.')
    rates = {**DEFAULT_DAY_RATES, **(day_rates or {})}
    for role in ROLES:
        _number(rates[role], f'{ROLE_LABELS[role]} daily rate')
    operator = s.company.startswith('operator_')
    legal_factor = 1.0
    if operator:
        if not isinstance(s.geolocation_enabled, bool) or not isinstance(s.apply_legality_to_setup, bool):
            raise ValueError('Geolocation and setup scope must be on or off.')
        _number(s.batch_dds, 'Consignments per DDS', 1)
        _number(s.legality_share, 'Legality share', 0, 1)
        _number(s.retained_legality_share, 'Legality effort retained', 0, 1)
        legal_factor = 1 - s.legality_share * (1 - s.retained_legality_share)
        factors.extend([
            {'factor': 'Local-laws factor on risk tasks', 'setup': legal_factor if s.apply_legality_to_setup else 1.0, 'annual': legal_factor},
            {'factor': 'Geolocation included', 'setup': int(s.geolocation_enabled), 'annual': int(s.geolocation_enabled)},
            {'factor': 'Consignments per DDS (variable effort only)', 'setup': 1.0, 'annual': s.batch_dds},
        ])
    volume_factors = {'suppliers': 1.0, 'receipts': 1.0}
    if s.company in REFERENCE_VOLUMES:
        for driver, default in zip(('suppliers', 'receipts'), REFERENCE_VOLUMES[s.company]):
            value = getattr(s, driver)
            ref = getattr(s, 'reference_' + driver)
            value = default if value is None else value
            ref = default if ref is None else ref
            volume_factors[driver] = _number(value, driver.title(), whole=True) / _number(ref, 'Reference ' + driver, 1, whole=True)
        factors.extend([
            {'factor': 'Supplier ratio (supplier tasks only)', 'setup': volume_factors['suppliers'], 'annual': volume_factors['suppliers']},
            {'factor': 'Receipt ratio (annual receipt task only)', 'setup': 1.0, 'annual': volume_factors['receipts']},
        ])
    tasks = get_tasks(s.company)
    overrides = task_days or {}
    inputs = {t.code: {role: overrides.get(t.code, {}).get(role, t.days[role]) for role in ROLES} for t in tasks}
    missing = []
    for t in tasks:
        for role, value in inputs[t.code].items():
            if value is None:
                missing.append(f'{t.code}: {role} days')
            else:
                _number(value, f'{t.code}: {role} days')
    if operator:
        for phase in ('S', 'O'):
            for role in ROLES:
                pool, geo = inputs[f'OP_{phase}_INFO'][role], inputs[f'OP_{phase}_GEO'][role]
                if pool is not None and geo is not None and geo > pool:
                    raise ValueError(f'{role} geolocation days cannot exceed the Article 9 information days ({"setup" if phase == "S" else "annual"}).')
    details = []
    geo = {'setup': [], 'ongoing': []}
    for task in tasks:
        multiplier = 1.0
        if task.mechanism == 'risk':
            multiplier = 0.0 if s.risk == 'low' else (legal_factor if task.phase == 'ongoing' or s.apply_legality_to_setup else 1.0)
        elif task.mechanism == 'geolocation':
            multiplier = float(s.geolocation_enabled)
        elif task.mechanism == 'dds_variable':
            multiplier = 1 / s.batch_dds
        elif task.mechanism in volume_factors:
            multiplier = volume_factors[task.mechanism]
        for role in ROLES:
            input_days = inputs[task.code][role]
            days = input_days
            if task.mechanism == 'information_pool':
                allocation = inputs['OP_S_GEO' if task.phase == 'setup' else 'OP_O_GEO'][role]
                days = None if days is None or allocation is None else days - allocation
            effective = None if days is None else days * multiplier
            cost = None if effective is None else effective * rates[role]
            final = None if cost is None else cost * scenario_factors[task.phase]
            details.append({
                'code': task.code, 'task': task.name, 'phase': task.phase, 'role': role,
                'input_days': input_days, 'effective_days': effective, 'day_rate': rates[role],
                'base_cost': cost, 'task_factor': (effective / input_days if input_days else multiplier) if effective is not None else None,
                'scenario_factor': scenario_factors[task.phase], 'final_cost': final,
            })
            if task.mechanism == 'geolocation':
                geo[task.phase].append(None if input_days is None else input_days * rates[role])
    phase_totals = {phase: _complete_sum(d['final_cost'] for d in details if d['phase'] == phase) for phase in ('setup', 'ongoing')}
    base_totals = {phase: _complete_sum(d['base_cost'] for d in details if d['phase'] == phase) for phase in ('setup', 'ongoing')}
    annual = phase_totals['ongoing']
    return Result(
        reason='Complete the pending role-day inputs to calculate the affected costs.' if missing else '',
        base_setup=base_totals['setup'], base_annual=base_totals['ongoing'],
        setup=phase_totals['setup'], annual=annual,
        annual_year3=None if annual is None or s.year3_efficiency is None else annual * (1 - s.year3_efficiency),
        total=_complete_sum(phase_totals.values()), geo_setup=_complete_sum(geo['setup']), geo_annual=_complete_sum(geo['ongoing']),
        details=details, factors=factors, missing_inputs=tuple(missing),
    )


def build_scenario_table(day_rates=None, task_days=None, settings: Settings | None = None) -> list[dict]:
    """Reproduce the workbook's three comparison and six Defra profiles.

    Shared Phase 2 controls and task edits are retained. Each profile supplies its
    own DD/commodity/complexity assumptions; Defra controls are independent of the
    currently selected company's custom scenario. Volumes edited for one group
    do not leak into the other downstream group.
    """
    current = settings or Settings()
    for attr in ('defra_dd_setup', 'defra_dd_annual', 'defra_complexity'):
        _number(getattr(current, attr), attr.replace('_', ' ').title())
    rows = []
    for case in _INPUTS['scenario_definitions']:
        defra = case['mode'] == 'defra'
        label = ('Defra ' + ('low' if case['risk'] == 'low' else 'standard/high') + f" risk, commodity factor {case['commodity_factor']:g}") if defra else 'Comparison ' + case['id'].rsplit('_', 1)[1]
        for group, sizes in COMPANY_SIZES.items():
            for size in sizes:
                same_group = group == current.company
                scenario = replace(
                    current, company=group, size=size,
                    risk='low' if case['risk'] == 'low' else 'standard_high',
                    dd_setup=current.defra_dd_setup if defra else case['dd_setup'],
                    dd_annual=current.defra_dd_annual if defra else case['dd_ongoing'],
                    complexity=current.defra_complexity if defra else case['operator_complexity'],
                    commodity=case['commodity_factor'], size_factor=None,
                    suppliers=current.suppliers if same_group else None,
                    receipts=current.receipts if same_group else None,
                    reference_suppliers=current.reference_suppliers if same_group else None,
                    reference_receipts=current.reference_receipts if same_group else None,
                    year3_efficiency=(current.year3_efficiency if defra else 0.1) if case['year3_applies'] else None,
                )
                result = calculate(scenario, day_rates, task_days)
                rows.append({
                    'case_id': case['id'], 'Scenario': label, 'Company': COMPANY_GROUPS[group], 'company': group, 'Size': size,
                    'Risk': 'Low' if scenario.risk == 'low' else 'Standard / high',
                    'Setup (£)': result.setup, 'Annual (£)': result.annual, 'Annual year 3 (£)': result.annual_year3,
                    'Setup + one annual (£)': result.total,
                    'Status': 'N/A' if not result.eligible else 'TBC' if result.missing_inputs else 'Calculated',
                })
    return rows
