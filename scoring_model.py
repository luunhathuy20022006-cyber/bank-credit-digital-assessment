
"""BCDS 2025: 12 financial criteria + D1/D2/D3 (research index, not credit rating)."""
from pathlib import Path
import json
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
OUT = ROOT / 'output'
BANKS = ['VCB', 'BID', 'CTG', 'TCB', 'MBB']

# Weights expressed in percentage points; total = 100.
CRITERIA = [
 ('NPL', 'NPL_%', 'credit', 14, 'low'),
 ('Group2', 'Group2_%', 'credit', 7, 'low'),
 ('LLR', 'LLR_NPL_%', 'credit', 8, 'high'),
 ('CoR', 'CoR_%', 'credit', 6, 'low'),
 ('CAR', 'CAR_%', 'capital', 7, 'high'),
 ('EquityAssets', 'Equity_Assets_%', 'capital', 5, 'high'),
 ('CASA', 'CASA_%', 'capital', 4, 'high'),
 ('DepositsLiabilities', 'Customer_Deposits_Liabilities_%', 'capital', 4, 'high'),
 ('ROA', 'ROA_%', 'profitability', 5, 'high'),
 ('ROE', 'ROE_%', 'profitability', 5, 'high'),
 ('NIM', 'NIM_%', 'profitability', 5, 'high'),
 ('CIR', 'CIR_%', 'profitability', 5, 'low'),
 ('D1', 'D1_score_0_3', 'digital', 25/3, 'fixed'),
 ('D2', 'D2_score_0_3', 'digital', 25/3, 'fixed'),
 ('D3', 'D3_score_0_3', 'digital', 25/3, 'fixed'),
]

GROUP_LABELS = {
 'credit':'Chất lượng tín dụng',
 'capital':'Vốn và nguồn vốn',
 'profitability':'Sinh lời và hiệu quả',
 'digital':'Chuyển đổi số'
}


def load_inputs(financial_path=None, digital_path=None, year=2025):
    financial_path = (
    Path(financial_path)
    if financial_path
    else ROOT / 'output' / 'credit_data.xlsx'
    )

    digital_path = (
    Path(digital_path)
    if digital_path
    else ROOT / 'digital_dataset_equal_2025.csv'
    )

    if financial_path.suffix.lower() in ('.xlsx', '.xls'):
        finance = pd.read_excel(financial_path, sheet_name='BCDS_Metrics')
    else:
        finance = pd.read_csv(financial_path)

    digital = pd.read_csv(digital_path)

    finance = finance.loc[finance['year'].eq(year)].copy()
    digital = digital.loc[digital['year'].eq(year)].copy()

    for label, frame, key in [
        ('financial', finance, 'ticker'),
        ('digital', digital, 'bank_code')
    ]:
        if frame[key].duplicated().any():
            raise ValueError(f'Duplicate {label} bank/year keys')
        if set(frame[key]) != set(BANKS):
            raise ValueError(
                f'{label}: expected {BANKS}; received {sorted(frame[key].tolist())}'
            )

    merged = finance.merge(
        digital,
        left_on=['ticker','year'],
        right_on=['bank_code','year'],
        how='inner',
        validate='one_to_one'
    )

    return merged.set_index('ticker').loc[BANKS].reset_index()


def score_banks(financial_path=None, digital_path=None, year=2025):
    raw = load_inputs(financial_path, digital_path, year)

    if abs(sum(c[3] for c in CRITERIA) - 100) > 1e-8:
        raise ValueError('Weights must sum to 100')

    for code in ('D1','D2','D3'):
        statuses = raw[f'{code}_status'].fillna('missing')
        if statuses.eq('missing').any():
            raise ValueError(
                f'{code}: missing digital evidence; '
                'cannot produce comparable full 15-indicator ranking'
            )

    detail_rows = []
    skipped = []

    for code, column, group, weight, direction in CRITERIA:
        values = pd.to_numeric(raw[column], errors='coerce')

        if values.isna().any():
            raise ValueError(
                f'{code}: missing/invalid values; do not replace NA with zero'
            )

        if direction == 'fixed':
            if (~values.isin([0,1,2,3])).any():
                raise ValueError(
                    f'{code}: score must be integer 0, 1, 2, 3'
                )
            normalized = values / 3
        else:
            span = values.max() - values.min()

            if np.isclose(span, 0):
                skipped.append(code)
                continue

            normalized = (
                (values - values.min()) / span
                if direction == 'high'
                else (values.max() - values) / span
            )

        for i, bank in raw.iterrows():
            detail_rows.append({
                'ticker': bank['ticker'],
                'bank': bank['bank'],
                'year': int(year),
                'criterion': code,
                'group': group,
                'group_label': GROUP_LABELS[group],
                'raw_value': float(values.iloc[i]),
                'normalized_0_1': float(normalized.iloc[i]),
                'base_weight': float(weight),
                'direction': direction,
                'status': (
                    bank.get(f'{code}_status', 'verified')
                    if group == 'digital'
                    else 'provided'
                )
            })

    detail = pd.DataFrame(detail_rows)

    # Remove identical indicators globally, then renormalize weights.
    active_weight = (
        detail[['criterion','base_weight']]
        .drop_duplicates()['base_weight']
        .sum()
    )

    detail['effective_weight'] = (
        detail['base_weight'] * 100 / active_weight
    )

    detail['weighted_score'] = (
        detail['normalized_0_1'] * detail['effective_weight']
    )

    groups = detail.groupby(
        ['ticker','bank','year','group','group_label'],
        as_index=False
    ).agg(
        group_score=('weighted_score','sum'),
        group_max=('effective_weight','sum')
    )

    groups['group_score_100'] = (
        groups['group_score'] / groups['group_max'] * 100
    )

    totals = detail.groupby(
        ['ticker','bank','year'],
        as_index=False
    ).agg(
        total_score=('weighted_score','sum')
    )

    totals['total_score'] = totals['total_score'].round(4)

    totals = totals.sort_values(
        ['total_score','ticker'],
        ascending=[False,True]
    ).reset_index(drop=True)

    totals['rank'] = (
        totals['total_score']
        .rank(method='min',ascending=False)
        .astype(int)
    )

    statuses = raw[['ticker','index_status']].copy()
    totals = totals.merge(statuses,on='ticker',how='left')

    totals['score_status'] = np.where(
        totals['index_status'].eq('verified'),
        'verified',
        'provisional_review'
    )

    return {
        'raw': raw,
        'details': detail,
        'groups': groups,
        'ranking': totals,
        'skipped': skipped
    }


def export_results(result, output_dir=None):
    output_dir = Path(output_dir) if output_dir else OUT
    output_dir.mkdir(parents=True,exist_ok=True)

    for key, filename in [
        ('raw','merged_dataset_2025.csv'),
        ('details','criterion_scores_2025.csv'),
        ('groups','group_scores_2025.csv'),
        ('ranking','bank_ranking_2025.csv')
    ]:
        result[key].to_csv(
            output_dir / filename,
            index=False,
            encoding='utf-8-sig'
        )

    (output_dir / 'scoring_metadata.json').write_text(
        json.dumps({
            'year': 2025,
            'criteria_count': 15,
            'digital_weights': 'equal_25_divided_by_3',
            'skipped_indicators': result['skipped'],
            'method': (
                'Min-Max for financial; score/3 for D1-D3; '
                'weights in points'
            ),
            'disclaimer': (
                'Research comparison only; digital evidence '
                'marked review is not independently verified.'
            )
        },ensure_ascii=False,indent=2),
        encoding='utf-8'
    )

    return output_dir


if __name__ == '__main__':
    result = score_banks()
    print(result['ranking'].to_string(index=False))
    print('Saved to:',export_results(result))
