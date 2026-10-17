"""Read exported files. Never import or execute the upstream pipeline."""
from pathlib import Path
import json

import pandas as pd
import streamlit as st

from config import BANKS, DIGITAL_CODES, PROJECT_ROOT, YEAR


class DataIssue(ValueError):
    """An actionable input problem that the UI can display locally."""


SPECS = {
    "ranking": ("output/bank_ranking_2025.csv", ("ticker", "bank", "year", "total_score", "rank"), ("ticker", "year")),
    "groups": ("output/group_scores_2025.csv", ("ticker", "bank", "year", "group", "group_label", "group_score", "group_max", "group_score_100"), ("ticker", "year", "group")),
    "criteria": ("output/criterion_scores_2025.csv", ("ticker", "bank", "year", "criterion", "group", "group_label", "raw_value", "normalized_0_1", "base_weight", "effective_weight", "weighted_score", "direction"), ("ticker", "year", "criterion")),
    "merged": ("output/merged_dataset_2025.csv", ("ticker", "bank", "year"), ("ticker", "year")),
    "digital": ("digital_dataset_equal_2025.csv", ("bank_code", "bank_name", "year", "D1_score_0_3", "D2_score_0_3", "D3_score_0_3"), ("bank_code", "year")),
    "evidence": ("digital_evidence_2025.csv", ("bank_code", "year", "indicator_code", "score_0_3"), ("bank_code", "year", "indicator_code")),
    "financial": ("output/credit_data_clean.csv", ("ticker", "bank", "year", "variable", "value_clean"), ("ticker", "year", "variable")),
}
NUMERIC = {
    "ranking": ("total_score", "rank"),
    "groups": ("group_score", "group_max", "group_score_100"),
    "criteria": ("raw_value", "normalized_0_1", "base_weight", "effective_weight", "weighted_score"),
    "digital": tuple(f"{code}_score_0_3" for code in DIGITAL_CODES),
    "evidence": ("score_0_3",), "financial": ("value_clean",),
}


def file_signature(path):
    path = Path(path).resolve()
    try:
        stat = path.stat()
        return str(path), stat.st_mtime_ns, stat.st_size
    except OSError as exc:
        raise DataIssue(f"Không tìm thấy hoặc không đọc được {path.name}. "
                        "Hãy kiểm tra output đã xuất; nếu chưa có, hãy chạy pipeline riêng trước khi mở Dashboard.") from exc


@st.cache_data(show_spinner=False, max_entries=48)
def _read_csv(path, modified_ns, size):
    # All signature arguments participate in cache invalidation.
    return pd.read_csv(path, encoding="utf-8-sig")


@st.cache_data(show_spinner=False, max_entries=8)
def _read_json(path, modified_ns, size):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


@st.cache_data(show_spinner=False, max_entries=12)
def _read_sheet(path, modified_ns, size, sheet):
    return pd.read_excel(path, sheet_name=sheet, engine="openpyxl")


def validate_frame(frame, required, keys, label, bank_column="ticker", financial=False):
    absent = set(required) - set(frame.columns)
    if absent:
        raise DataIssue(f"{label}: thiếu cột bắt buộc: {', '.join(sorted(absent))}.")
    if frame.empty:
        raise DataIssue(f"{label}: không có dữ liệu.")
    if frame[list(keys)].isna().any().any():
        raise DataIssue(f"{label}: khóa định danh bị thiếu.")
    if frame.duplicated(list(keys)).any():
        raise DataIssue(f"{label}: trùng khóa {', '.join(keys)}.")
    if bank_column and set(frame[bank_column]) != set(BANKS):
        raise DataIssue(f"{label}: tập mã ngân hàng không khớp dữ liệu nghiên cứu 5 ngân hàng.")
    if "year" in frame and (YEAR not in set(frame.year) or (not financial and set(frame.year) != {YEAR})):
        raise DataIssue(f"{label}: dữ liệu năm không phù hợp năm đánh giá {YEAR}.")
    return frame


def _load(kind, root=None):
    relative, required, keys = SPECS[kind]
    path = Path(root or PROJECT_ROOT) / relative
    try:
        frame = _read_csv(*file_signature(path))
        validate_frame(frame, required, keys, relative,
                       "bank_code" if kind in ("digital", "evidence") else "ticker",
                       financial=kind == "financial")
        for column in NUMERIC.get(kind, ()):
            converted = pd.to_numeric(frame[column], errors="coerce")
            if (frame[column].notna() & (converted.isna() | converted.isin([float("inf"), -float("inf")]))).any():
                raise DataIssue(f"{relative}: cột {column} có giá trị số không hợp lệ.")
        if kind in ("groups", "criteria", "evidence"):
            bank_key, item_key = ("bank_code", "indicator_code") if kind == "evidence" else ("ticker", "group" if kind == "groups" else "criterion")
            universe = set(frame[item_key])
            if any(set(part[item_key]) != universe for _, part in frame.groupby(bank_key)):
                raise DataIssue(f"{relative}: không đồng nhất độ phủ tiêu chí/nhóm giữa các ngân hàng.")
        if kind in ("digital", "evidence"):
            for column in NUMERIC[kind]:
                if not frame[column].dropna().isin([0, 1, 2, 3]).all():
                    raise DataIssue(f"{relative}: {column} nằm ngoài thang 0–3.")
        return frame.copy(deep=True)
    except DataIssue:
        raise
    except (OSError, ValueError, KeyError, UnicodeError) as exc:
        raise DataIssue(f"Không đọc được {relative}: {exc}") from exc


def load_ranking(root=None):
    return _load("ranking", root)


def load_group_scores(root=None):
    return _load("groups", root)


def load_criterion_scores(root=None):
    return _load("criteria", root)


def load_merged_data(root=None):
    return _load("merged", root)


def load_digital_dataset(root=None):
    return _load("digital", root)


def load_digital_evidence(root=None):
    return _load("evidence", root)


def load_financial_sources(root=None):
    return _load("financial", root)


def load_scoring_metadata(root=None):
    path = Path(root or PROJECT_ROOT) / "output/scoring_metadata.json"
    try:
        data = _read_json(*file_signature(path))
        if not isinstance(data, dict) or data.get("year") != YEAR or not isinstance(data.get("criteria_count"), int):
            raise DataIssue("scoring_metadata.json: năm hoặc số tiêu chí không hợp lệ.")
        return data
    except DataIssue:
        raise
    except (OSError, ValueError) as exc:
        raise DataIssue(f"Không đọc được scoring_metadata.json: {exc}") from exc


def load_workbook_sheet(sheet, root=None):
    try:
        path = Path(root or PROJECT_ROOT) / "output/credit_data.xlsx"
        return _read_sheet(*file_signature(path), sheet).copy(deep=True)
    except DataIssue:
        raise
    except (OSError, ValueError, KeyError, ImportError) as exc:
        raise DataIssue(f"Không đọc được sheet {sheet}: {exc}") from exc


def select_bank(frame, ticker, column="ticker"):
    if ticker not in set(frame[column]):
        raise DataIssue(f"Mã ngân hàng không hợp lệ: {ticker}.")
    return frame.loc[frame[column].eq(ticker)].copy()


def get_bank_summary(ticker, root=None):
    return select_bank(load_ranking(root), ticker).iloc[0].to_dict()


def get_bank_group_scores(ticker, root=None):
    return select_bank(load_group_scores(root), ticker)


def get_bank_criterion_scores(ticker, root=None):
    return select_bank(load_criterion_scores(root), ticker)


def get_digital_evidence(ticker, root=None):
    return select_bank(load_digital_evidence(root), ticker, "bank_code")


def filter_criteria(frame, ticker, group=None, kind="Tất cả"):
    selected = select_bank(frame, ticker)
    if group:
        selected = selected.loc[selected.group.eq(group)]
    if kind == "Định lượng":
        selected = selected.loc[~selected.criterion.isin(DIGITAL_CODES)]
    elif kind == "Định tính":
        selected = selected.loc[selected.criterion.isin(DIGITAL_CODES)]
    return selected.copy()


def extreme_groups(frame, column="group_score_100", highest=True):
    valid = frame.dropna(subset=[column])
    if valid.empty:
        return []
    extreme = valid[column].max() if highest else valid[column].min()
    return valid.loc[valid[column].eq(extreme), "group_label"].tolist()


def refresh_data():
    _read_csv.clear()
    _read_json.clear()
    _read_sheet.clear()
