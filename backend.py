
"""Backend functions for the BCDS Streamlit dashboard."""

from functools import lru_cache
from scoring_model import score_banks, export_results, BANKS


@lru_cache(maxsize=4)
def _data(year=2025):
    if year != 2025:
        raise ValueError('Current dataset supports 2025 only')

    return score_banks(year=year)


def get_ranking(year=2025):
    """Get the overall ranking of all five banks."""
    return _data(year)['ranking'].copy()


def get_bank_detail(ticker, year=2025):
    """Get the total, criterion, and group scores for one bank."""
    ticker = str(ticker).upper()

    if ticker not in BANKS:
        raise ValueError(
            f'Unknown bank {ticker}. Expected one of {BANKS}'
        )

    data = _data(year)

    return {
        'summary': (
            data['ranking']
            .loc[data['ranking']['ticker'].eq(ticker)]
            .iloc[0]
            .to_dict()
        ),
        'criteria': (
            data['details']
            .loc[data['details']['ticker'].eq(ticker)]
            .copy()
        ),
        'groups': (
            data['groups']
            .loc[data['groups']['ticker'].eq(ticker)]
            .copy()
        ),
    }


def get_group_comparison(year=2025):
    """Get group scores for comparing banks."""
    return _data(year)['groups'].copy()


def get_criterion_comparison(criterion, year=2025):
    """Compare banks by a selected criterion."""
    criterion = str(criterion).strip()

    data = _data(year)['details']
    found = data.loc[data['criterion'].eq(criterion)]

    if found.empty:
        raise ValueError(f'Unknown criterion: {criterion}')

    return found.copy()


def refresh_scores(year=2025):
    """Recalculate scores and export updated results."""
    _data.cache_clear()

    result = _data(year)
    export_results(result)

    return result['ranking'].copy()
