"""
CREDIT DATA PIPELINE 2024-2025
==============================
Banks: TCB, CTG, BID, VCB, MBB

Mục tiêu:
1. Crawl toàn bộ Balance Sheet/Income Statement từ VNStock; Raw sheets chỉ xuất 2024-2025 và chuẩn hóa nhãn năm. 2025 là năm chính; dữ liệu 2024 được dùng để tính các giá trị bình quân cho CoR, ROA và ROE.
2. Bổ sung tổng dư nợ phân loại Nhóm 1-5, Group 2-5 và CAR 2025 từ nguồn chính thức đã đối chiếu.
3. Chuẩn hóa dữ liệu, kiểm tra missing/consistency.
4. Tính các chỉ tiêu dùng trong bộ BCDS:
   - NPL
   - Group 2 Ratio
   - LLR/NPL
   - CoR
   - CAR
   - ....
5. Xuất:
   - output/credit_data.xlsx
   - output/credit_data_clean.csv

Lưu ý:
- Không thay dữ liệu thiếu bằng 0.
"""

from pathlib import Path
import platform
import sys

import pandas as pd


# ============================================================
# 1. PROJECT CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "credit_data.xlsx"
CLEAN_CSV_FILE = OUTPUT_DIR / "credit_data_clean.csv"

BANKS = {
    "Techcombank": "TCB",
    "VietinBank": "CTG",
    "BIDV": "BID",
    "Vietcombank": "VCB",
    "MBBank": "MBB",
}


TARGET_YEARS = [2024, 2025]

# Chỉ giữ các biến VNStock thật sự cần cho phần credit.
VNSTOCK_VARIABLE_MAP = {
    "total_loans": {
        "sheet": "balance_sheet",
        "item_id": "BS_LOANS_TO_CUSTOMERS",
        "unit": "ty_dong",
    },
    "credit_risk_provision": {
        "sheet": "balance_sheet",
        "item_id": "provisions_for_losses_on_loans_advances_and_finance_leases_to_customers",
        "unit": "ty_dong",
        "absolute": True,
    },
    "provision_expense": {
        "sheet": "income_statement",
        "item_id": "provision_for_credit_losses",
        "unit": "ty_dong",
        "absolute": True,
    },
}

# Input bắt buộc theo bộ tiêu chí credit.
CREDIT_REQUIRED = {
    2024: ["total_loans"],
    2025: [
        "total_loans",
        "classified_loans",
        "group_2_loans",
        "group_3_loans",
        "group_4_loans",
        "group_5_loans",
        "credit_risk_provision",
        "provision_expense",
        "car",
    ],
}


# ============================================================
# 2. VERIFIED SUPPLEMENTS 2025
# ============================================================
# Group 2-5: tỷ đồng.
# CAR: %.
# Các biến này không có trong mapping VNStock hiện tại nên được
# bổ sung từ BCTC hợp nhất kiểm toán 2025 và CBTT CAR 31/12/2025
# theo đúng bộ nguồn chính thức do nhóm thu thập.

CREDIT_SUPPLEMENTS_2025 = {
    "Techcombank": {
        # Thuyết minh 9.1: tổng dư nợ được phân loại Nhóm 1-5
        "classified_loans": (731955.772, "ty_dong"),
        "group_2_loans": (3852.272, "ty_dong"),
        "group_3_loans": (918.063, "ty_dong"),
        "group_4_loans": (1339.119, "ty_dong"),
        "group_5_loans": (5941.193, "ty_dong"),
        # CBTT CAR 31/12/2025: CAR hợp nhất = 14,61%.
        "car": (14.61, "%"),
    },
    "VietinBank": {
        # Thuyết minh 8.3: tổng dư nợ được phân loại Nhóm 1-5
        "classified_loans": (1992272.868, "ty_dong"),
        "group_2_loans": (17345.911, "ty_dong"),
        "group_3_loans": (1490.975, "ty_dong"),
        "group_4_loans": (578.479, "ty_dong"),
        "group_5_loans": (19846.742, "ty_dong"),
        # CBTT CAR 31/12/2025: CAR hợp nhất = 9,89%.
        "car": (9.89, "%"),
    },
    "BIDV": {
        # Phân tích chất lượng nợ cho vay: tổng Nhóm 1-5
        "classified_loans": (2372955.074, "ty_dong"),
        "group_2_loans": (31462.771, "ty_dong"),
        "group_3_loans": (4473.881, "ty_dong"),
        "group_4_loans": (4677.985, "ty_dong"),
        "group_5_loans": (25824.953, "ty_dong"),
        # CBTT CAR 31/12/2025: CAR hợp nhất = 9,18%.
        "car": (9.18, "%"),
    },
    "Vietcombank": {
        # Phân tích chất lượng nợ cho vay: tổng Nhóm 1-5
        "classified_loans": (1673525.675, "ty_dong"),
        "group_2_loans": (2704.636, "ty_dong"),
        "group_3_loans": (760.561, "ty_dong"),
        "group_4_loans": (222.632, "ty_dong"),
        "group_5_loans": (8686.362, "ty_dong"),
        # Basel II/Pillar 3 tại 31/12/2025: CAR hợp nhất = 11,56%.
        "car": (11.56, "%"),
    },
    "MBBank": {
        # Thuyết minh 9.1: tổng dư nợ phân tích chất lượng nợ,
        # bao gồm khoản cho vay giao dịch ký quỹ/ứng trước thuộc nợ đủ tiêu chuẩn.
        "classified_loans": (1098100.630, "ty_dong"),
        "group_2_loans": (10210.040, "ty_dong"),
        "group_3_loans": (3276.216, "ty_dong"),
        "group_4_loans": (4330.016, "ty_dong"),
        "group_5_loans": (6421.264, "ty_dong"),
        # CBTT CAR 31/12/2025: CAR hợp nhất = 11,02%.
        "car": (11.02, "%"),
    },
}

# Chỉ tiêu bổ sung cho nhóm Vốn & nguồn vốn / Sinh lời & hiệu quả.
# CASA dùng số liệu so sánh từ BCTN MB 2025 (nguồn: BCTC hợp nhất các ngân hàng).
# NIM ưu tiên số công bố chính thức của từng ngân hàng khi có.
FINANCIAL_RATIO_SUPPLEMENTS_2025 = {
    "Techcombank": {"casa": 35.9, "nim": 3.8},
    "VietinBank": {"casa": 25.5, "nim": 2.6},
    "BIDV": {"casa": 21.8, "nim": 2.1},
    "Vietcombank": {"casa": 35.4, "nim": 2.9},
    "MBBank": {"casa": 37.8, "nim": 3.9},
}



FINANCIAL_REQUIRED = {
    2024: [
        "total_assets",
        "equity",
    ],
    2025: [
        "total_assets",
        "equity",
        "customer_deposits",
        "total_liabilities",
        "net_profit",
        "operating_expenses",
        "total_operating_income",
        "casa",
        "nim",
    ],
}

FINANCIAL_RATIO_SOURCES = {
    "casa": (
        "MBBank - Báo cáo thường niên 2025, biểu đồ CASA so sánh các ngân hàng",
        "https://www.mbbank.com.vn/resources/files/NhaDauTu/2026/T03-2026/20260330---mbb---bao-cao-thuong-nien-2025.pdf",
    ),
    "nim": {
        "Techcombank": (
            "Techcombank - Kết quả kinh doanh FY2025",
            "https://techcombank.com/nha-dau-tu/thong-tin-tai-chinh/chi-so-noi-bat",
        ),
        "VietinBank": (
            "VietinBank - Báo cáo thường niên 2025",
            "https://investor.vietinbank.vn/en/w/cbtt-bao-cao-thuong-nien-2025-cua-vietinbank",
        ),
        "BIDV": (
            "MBBank - Báo cáo thường niên 2025, biểu đồ NIM so sánh các ngân hàng",
            "https://www.mbbank.com.vn/resources/files/NhaDauTu/2026/T03-2026/20260330---mbb---bao-cao-thuong-nien-2025.pdf",
        ),
        "Vietcombank": (
            "Vietcombank - Investor Presentation 1Q2026 (số FY2025)",
            "https://www.vietcombank.com.vn/-/media/Project/VCB-Sites/VCB/Nha-Dau-tu/Files/KQKD-quy/2026/1Q2026_VCB-Investors-Presentation---VIE-PUBLIC.pdf",
        ),
        "MBBank": (
            "MBBank - Báo cáo thường niên 2025",
            "https://www.mbbank.com.vn/resources/files/NhaDauTu/2026/T03-2026/20260330---mbb---bao-cao-thuong-nien-2025.pdf",
        ),
    },
}


CREDIT_SUPPLEMENT_SOURCES = {
    "Techcombank": {
        "debt": (
            "Techcombank - BCTC hợp nhất kiểm toán 2025, Thuyết minh 9.1 Phân tích chất lượng nợ cho vay",
            "https://techcombank.com/content/dam/techcombank/public-site/documents/"
            "techcombank-vas-bao-cao-tai-chinh-hop-nhat-ye25.pdf",
        ),
        "car": (
            "Techcombank - Công bố thông tin tỷ lệ an toàn vốn 31/12/2025",
            "https://techcombank.com/content/dam/techcombank/public-site/documents/"
            "ty-le-an-toan-von-2h2025-final.pdf",
        ),
    },
    "VietinBank": {
        "debt": (
            "VietinBank - BCTC hợp nhất kiểm toán năm 2025, Thuyết minh 8.3 Theo chất lượng nợ cho vay",
            "https://investor.vietinbank.vn/documents/20126/667477/"
            "BCTC%20hop%20nhat%20kiem%20toan%20nam%202025_VN.pdf.pdf/"
            "4c8eda02-b420-612d-24ac-c12f2bbd3451",
        ),
        "car": (
            "VietinBank - Báo cáo công bố thông tin về tỷ lệ an toàn vốn tại 31/12/2025",
            "https://investor.vietinbank.vn/documents/20126/0/"
            "CBTT+ty+le+an+toan+von+31.12.2025.pdf/"
            "40bc76b5-2005-b371-2e46-18ae3e0d941d?t=1778467033969",
        ),
    },
    "BIDV": {
        "debt": (
            "BIDV - BCTC kiểm toán hợp nhất năm 2025, Phân tích chất lượng nợ cho vay",
            "https://bidv.com.vn/wps/wcm/connect/f40205f8-b854-48ab-aab5-e3bfcb5d7d40/"
            "20260330+-+BID+-+CBTT+BCTC+HN+2025.pdf?"
            "MOD=AJPERES&CACHEID=ROOTWORKSPACE-f40205f8-b854-48ab-aab5-e3bfcb5d7d40-pR1RUJh",
        ),
        "car": (
            "BIDV - Báo cáo công bố thông tin về tỷ lệ an toàn vốn kỳ 31/12/2025",
            "https://bidv.com.vn/wps/wcm/connect/af70916c-f5ef-41f3-8cd7-6431ad0b8d53/"
            "Bao+cao+CBTT_31.12.2025_VIE.pdf?"
            "MOD=AJPERES&CACHEID=ROOTWORKSPACE-af70916c-f5ef-41f3-8cd7-6431ad0b8d53-pS.k1MH",
        ),
    },
    "Vietcombank": {
        "debt": (
            "Vietcombank - BCTC hợp nhất kiểm toán năm 2025, Phân tích chất lượng nợ cho vay",
            "https://www.vietcombank.com.vn/-/media/Project/VCB-Sites/VCB/Nha-Dau-tu/"
            "Files/BC-dinh-ky/BCTC/2025/"
            "20260327---VCB---BCTC-hop-nhat-kiem-toan-nam-2025.pdf?ts=00010101000000",
        ),
        "car": (
            "Vietcombank - Báo cáo công bố thông tin theo Trụ cột 3 Basel II tại 31/12/2025",
            "https://www.vietcombank.com.vn/-/media/Project/VCB-Sites/VCB/Nha-Dau-tu/"
            "Files/Cong-bo-thong-tin/Thong-tin-cong-bo/2026/"
            "BC_CBTT_BASEL_II_31122025.pdf?ts=00010101000000",
        ),
    },
    "MBBank": {
        "debt": (
            "MBBank - BCTC kiểm toán hợp nhất năm 2025, Thuyết minh 9.1 Phân tích chất lượng nợ cho vay",
            "https://www.mbbank.com.vn/resources/files/NhaDauTu/2026/T03-2026/"
            "20260310---mbb---bao-cao-tai-chinh-kiem-toan-hop-nhat-nam-2025.pdf",
        ),
        "car": (
            "MBBank - Công bố tỷ lệ an toàn vốn tại ngày 31/12/2025",
            "https://www.mbbank.com.vn/resources/files/NhaDauTu/2026/T05-2026/"
            "20260527---mbb---cbtt-ty-le-an-toan-von-tai-ngay-31122025-(vn-en).pdf",
        ),
    },
}


# Raw/detail supplements needed because VNStock v5 Community exposes a summarized
# statement schema. Monetary values are billion VND and were previously verified
# against the audited 2025 statements used by this project.
DETAIL_SUPPLEMENTS = {
    "Techcombank": {
        (2024, "total_loans"): 631724.964, (2025, "total_loans"): 767617.129,
        (2025, "credit_risk_provision"): 10498.378, (2025, "provision_expense"): 4420.625,
        (2025, "customer_deposits"): 618911.535, (2025, "operating_expenses"): 16432.434,
        (2025, "total_operating_income"): 53391.125,
    },
    "VietinBank": {
        (2024, "total_loans"): 1721954.714, (2025, "total_loans"): 1992272.868,
        (2025, "credit_risk_provision"): 34810.365, (2025, "provision_expense"): 17298.056,
        (2025, "customer_deposits"): 1793732.057, (2025, "operating_expenses"): 26552.924,
        (2025, "total_operating_income"): 87294.789,
    },
    "BIDV": {
        (2024, "total_loans"): 2056082.420, (2025, "total_loans"): 2372955.074,
        (2025, "credit_risk_provision"): 34945.553, (2025, "provision_expense"): 22998.662,
        (2025, "customer_deposits"): 2222991.628, (2025, "operating_expenses"): 30427.752,
        (2025, "total_operating_income"): 91213.932,
    },
    "Vietcombank": {
        (2024, "total_loans"): 1449198.899, (2025, "total_loans"): 1673525.675,
        (2025, "credit_risk_provision"): 24975.679, (2025, "provision_expense"): 3192.186,
        (2025, "customer_deposits"): 1672534.846, (2025, "operating_expenses"): 25242.799,
        (2025, "total_operating_income"): 72454.622,
    },
    "MBBank": {
        (2024, "total_loans"): 776657.846, (2025, "total_loans"): 1084019.370,
        (2025, "credit_risk_provision"): 13150.593, (2025, "provision_expense"): 13743.504,
        (2025, "customer_deposits"): 921368.132, (2025, "operating_expenses"): 19681.153,
        (2025, "total_operating_income"): 67693.015,
    },
}

# ============================================================
# 3. VNSTOCK
# ============================================================

def print_environment():
    print("=" * 70)
    print("BANK CREDIT DATA COLLECTOR")
    print("=" * 70)
    print(f"Python : {sys.version.split()[0]}")
    print(f"OS     : {platform.system()}")
    print(f"Project: {BASE_DIR}")

    if sys.version_info < (3, 10):
        raise RuntimeError("Project yêu cầu Python >= 3.10.")


def load_vnstock():
    try:
        from vnstock import Fundamental
        print("[OK] VNStock đã sẵn sàng.")
        return Fundamental
    except ImportError:
        print("[ERROR] Không tìm thấy VNStock.")
        print("Chạy: python -m pip install -r requirements.txt")
        raise


def normalize_dataframe(df, bank, ticker, report_type):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    result = df.copy()
    result.insert(0, "bank", bank)
    result.insert(1, "ticker", ticker)
    result.insert(2, "report_type", report_type)
    return result


def crawl_bank(Fundamental, bank, ticker):
    print(f"\n--- {bank} ({ticker}) ---")
    finance = Fundamental().equity(ticker)

    results = {
        "balance_sheet": pd.DataFrame(),
        "income_statement": pd.DataFrame(),
    }

    try:
        df = finance.balance_sheet(period="year", format="long")
        results["balance_sheet"] = normalize_dataframe(
            df, bank, ticker, "balance_sheet"
        )
        print(f"[OK] Balance Sheet: {len(results['balance_sheet'])} dòng")
    except Exception as error:
        print(f"[ERROR] Balance Sheet: {error}")

    try:
        df = finance.income_statement(period="year", format="long")
        results["income_statement"] = normalize_dataframe(
            df, bank, ticker, "income_statement"
        )
        print(f"[OK] Income Statement: {len(results['income_statement'])} dòng")
    except Exception as error:
        print(f"[ERROR] Income Statement: {error}")

    return results


def combine_frames(frames):
    valid = [
        df for df in frames
        if isinstance(df, pd.DataFrame) and not df.empty
    ]
    return pd.concat(valid, ignore_index=True) if valid else pd.DataFrame()


# ============================================================
# 4. CLEAN + STANDARDIZE
# ============================================================

def convert_to_billion_vnd(value):
    if pd.isna(value):
        return None
    try:
        return float(value) / 1_000_000_000
    except (TypeError, ValueError):
        return None


def extract_vnstock_value(df, bank, config, year):

    if df is None or df.empty or "bank" not in df.columns:
        return None, None

    # ---------- VNStock v5 long/tidy ----------
    if {"period", "value"}.issubset(df.columns):
        id_column = next(
            (col for col in ("id", "item_id") if col in df.columns),
            None,
        )
        if id_column is None:
            return None, None

        period_numeric = pd.to_numeric(df["period"], errors="coerce")
        rows = df[
            (df["bank"] == bank)
            & (df[id_column] == config["item_id"])
            & (period_numeric == int(year))
        ].copy()

        rows = rows[rows["value"].notna()]
        if rows.empty:
            return None, None

        row = rows.iloc[0]
        raw_value = pd.to_numeric(row["value"], errors="coerce")
        if pd.isna(raw_value):
            return None, None

        label = row.get("name", row.get("item", ""))
        source_field = "value"
        schema = "long"

    # ---------- Legacy / compatibility wide ----------
    else:
        id_column = next(
            (col for col in ("item_id", "id") if col in df.columns),
            None,
        )
        if id_column is None:
            return None, None

        rows = df[
            (df["bank"] == bank)
            & (df[id_column] == config["item_id"])
        ].copy()

        if rows.empty:
            return None, None

        # Chỉ nhận các cột có tên là năm 4 chữ số.
        year_columns = [
            col for col in df.columns
            if str(col).isdigit() and len(str(col)) == 4
        ]
        if not year_columns:
            return None, None

        year_numbers_in_output_order = [int(str(col)) for col in year_columns]
        sorted_years = sorted(year_numbers_in_output_order)

        # Theo tài liệu VNStock wide chuẩn: kỳ cũ -> kỳ mới.
        # Nếu header cũng tăng dần, nhãn năm là đúng.
        if year_numbers_in_output_order == sorted_years:
            year_to_source_column = {
                int(str(col)): col for col in year_columns
            }
            mapping_note = "wide_header_year"
        else:
            # Output legacy đang gặp: header giảm dần nhưng chuỗi giá trị vẫn
            # được xếp kỳ cũ -> kỳ mới. Ánh xạ theo vị trí, không hard-code năm.
            year_to_source_column = dict(zip(sorted_years, year_columns))
            mapping_note = "wide_position_normalized"

        source_field = year_to_source_column.get(int(year))
        if source_field is None:
            return None, None

        row = rows.iloc[0]
        raw_value = pd.to_numeric(row[source_field], errors="coerce")
        if pd.isna(raw_value):
            return None, None

        label = row.get("item", row.get("name", ""))
        schema = mapping_note

    raw_value = float(raw_value)

    if config.get("absolute", False):
        raw_value = abs(raw_value)

    value_clean = convert_to_billion_vnd(raw_value)

    evidence = (
        f"{label} "
        f"[{id_column}={config['item_id']}; "
        f"target_year={year}; source_field={source_field}; schema={schema}]"
    )

    return value_clean, evidence



def normalize_raw_years(df):
    """
    Chuẩn hóa Raw VNStock chỉ còn 2024-2025.

    Môi trường hiện tại trả wide với header 2025, 2024, 2023, 2022
    nhưng đối chiếu BCTC cho thấy chuỗi giá trị đi theo kỳ cũ -> kỳ mới.
    Hàm dùng cùng quy tắc positional mapping với extract_vnstock_value(),
    sau đó xuất nhãn năm thực 2024 và 2025.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    result = df.copy()

    # Nếu VNStock thực sự trả long/tidy thì lọc trực tiếp kỳ 2024-2025.
    if {"period", "value"}.issubset(result.columns):
        period_numeric = pd.to_numeric(result["period"], errors="coerce")
        result = result[period_numeric.isin(TARGET_YEARS)].copy()
        result["period"] = pd.to_numeric(result["period"], errors="coerce").astype("Int64")
        result = result.rename(columns={"period": "year"})
        return result.reset_index(drop=True)

    # Wide schema: nhận diện các cột năm và chuẩn hóa theo cùng logic extraction.
    year_columns = [
        col for col in result.columns
        if str(col).isdigit() and len(str(col)) == 4
    ]
    if not year_columns:
        return result.reset_index(drop=True)

    year_numbers_in_output_order = [int(str(col)) for col in year_columns]
    sorted_years = sorted(year_numbers_in_output_order)

    if year_numbers_in_output_order == sorted_years:
        year_to_source_column = {int(str(col)): col for col in year_columns}
    else:
        year_to_source_column = dict(zip(sorted_years, year_columns))

    non_year_columns = [col for col in result.columns if col not in year_columns]
    normalized = result[non_year_columns].copy()

    # Chỉ giữ đúng hai năm bài cần và đặt tên theo NĂM THỰC.
    for year in TARGET_YEARS:
        source_col = year_to_source_column.get(year)
        normalized[str(year)] = result[source_col] if source_col is not None else pd.NA

    return normalized.reset_index(drop=True)

def create_clean_vnstock_data(balance_all, income_all):
    """
    Phạm vi dữ liệu VNStock dùng cho phần credit:

    2025:
        - total_loans
        - credit_risk_provision
        - provision_expense

    2024:
        - total_loans
          Chỉ dùng cùng total_loans 2025 để tính average loans cho CoR.

    Các biến phân loại nợ (Group 2, Group 3-5, classified_loans)
    và CAR được bổ sung từ nguồn công bố chính thức.
    """
    rows = []

    source_frames = {
        "balance_sheet": balance_all,
        "income_statement": income_all,
    }

    needed_from_vnstock = {
        2025: [
            "total_loans",
            "credit_risk_provision",
            "provision_expense",
        ],
        2024: [
            "total_loans",
        ],
    }

    for bank, ticker in BANKS.items():
        for year, variables in needed_from_vnstock.items():
            for variable in variables:
                config = VNSTOCK_VARIABLE_MAP[variable]

                value, evidence = extract_vnstock_value(
                    source_frames[config["sheet"]],
                    bank,
                    config,
                    year,
                )

                supplement = DETAIL_SUPPLEMENTS.get(bank, {}).get((year, variable))
                if supplement is not None:
                    value = supplement
                    evidence = (
                        f"Audited-report detail supplement; variable={variable}; "
                        f"target_year={year}; value={supplement} ty_dong. "
                        "Used because VNStock v5 Community is summarized or the displayed loan line is net."
                    )

                rows.append({
                    "bank": bank,
                    "ticker": ticker,
                    "year": year,
                    "variable": variable,
                    "value_clean": value,
                    "unit_clean": config["unit"],
                    "source": "Official audited report supplement" if supplement is not None else "VNStock",
                    "source_title": CREDIT_SUPPLEMENT_SOURCES[bank]["debt"][0] if supplement is not None else None,
                    "source_url": CREDIT_SUPPLEMENT_SOURCES[bank]["debt"][1] if supplement is not None else None,
                    "evidence_text": evidence,
                    "status": "verified_supplement" if supplement is not None else ("verified" if value is not None else "missing"),
                })

    return pd.DataFrame(rows)


def add_credit_supplements(clean):
    rows = []

    for bank, values in CREDIT_SUPPLEMENTS_2025.items():
        ticker = BANKS[bank]

        for variable, (value, unit) in values.items():
            existing = clean[
                (clean["bank"] == bank)
                & (clean["year"] == 2025)
                & (clean["variable"] == variable)
                & clean["value_clean"].notna()
            ]

            if not existing.empty:
                continue

            source_key = "car" if variable == "car" else "debt"
            source_title, source_url = CREDIT_SUPPLEMENT_SOURCES[bank][source_key]

            rows.append({
                "bank": bank,
                "ticker": ticker,
                "year": 2025,
                "variable": variable,
                "value_clean": value,
                "unit_clean": unit,
                "source": "Official disclosure / audited report",
                "source_title": source_title,
                "source_url": source_url,
                "evidence_text": (
                    f"{source_title}; variable={variable}; "
                    f"value={value} {unit}"
                ),
                "status": "verified_supplement",
            })

    if rows:
        clean = pd.concat(
            [clean, pd.DataFrame(rows)],
            ignore_index=True,
            sort=False,
        )

    return clean


def create_credit_clean_data(clean):
    rows = []

    for bank, ticker in BANKS.items():
        for year, variables in CREDIT_REQUIRED.items():
            for variable in variables:
                hit = clean[
                    (clean["bank"] == bank)
                    & (clean["year"] == year)
                    & (clean["variable"] == variable)
                ]

                if hit.empty:
                    rows.append({
                        "bank": bank,
                        "ticker": ticker,
                        "year": year,
                        "variable": variable,
                        "value_clean": None,
                        "unit_clean": "%" if variable == "car" else "ty_dong",
                        "source": None,
                        "source_title": None,
                        "source_url": None,
                        "evidence_text": None,
                        "status": "missing",
                    })
                else:
                    row = hit.iloc[0].to_dict()
                    row["ticker"] = ticker
                    if pd.isna(row.get("value_clean")):
                        row["status"] = "missing"
                    rows.append(row)

    result = pd.DataFrame(rows)
    return result.sort_values(
        ["bank", "year", "variable"]
    ).reset_index(drop=True)


# ============================================================
# 5. CREDIT METRICS
# ============================================================

def one_value(clean, bank, year, variable):
    hit = clean[
        (clean["bank"] == bank)
        & (clean["year"] == year)
        & (clean["variable"] == variable)
        & clean["value_clean"].notna()
    ]

    if hit.empty:
        return None

    values = pd.to_numeric(
        hit["value_clean"], errors="coerce"
    ).dropna().unique()

    if len(values) != 1:
        return None

    return float(values[0])


def safe_pct(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator * 100


def calculate_credit_metrics(credit_clean):
    rows = []

    for bank, ticker in BANKS.items():
        loans_2024 = one_value(
            credit_clean, bank, 2024, "total_loans"
        )
        loans_2025 = one_value(
            credit_clean, bank, 2025, "total_loans"
        )
        classified_loans_2025 = one_value(
            credit_clean, bank, 2025, "classified_loans"
        )
        g2 = one_value(
            credit_clean, bank, 2025, "group_2_loans"
        )
        g3 = one_value(
            credit_clean, bank, 2025, "group_3_loans"
        )
        g4 = one_value(
            credit_clean, bank, 2025, "group_4_loans"
        )
        g5 = one_value(
            credit_clean, bank, 2025, "group_5_loans"
        )
        llp = one_value(
            credit_clean, bank, 2025, "credit_risk_provision"
        )
        provision_expense = one_value(
            credit_clean, bank, 2025, "provision_expense"
        )
        car = one_value(
            credit_clean, bank, 2025, "car"
        )

        npl_amount = (
            g3 + g4 + g5
            if all(x is not None for x in [g3, g4, g5])
            else None
        )

        average_loans = (
            (loans_2024 + loans_2025) / 2
            if loans_2024 is not None and loans_2025 is not None
            else None
        )

        rows.append({
            "bank": bank,
            "ticker": ticker,
            "NPL_%": safe_pct(npl_amount, classified_loans_2025),
            "Group2_%": safe_pct(g2, classified_loans_2025),
            "LLR_NPL_%": safe_pct(llp, npl_amount),
            "CoR_%": safe_pct(provision_expense, average_loans),
            "CAR_%": car,
        })

    return pd.DataFrame(rows)


def raw_value(df, bank, item_id, year):
    """Read a raw VNStock value from v5 long/tidy or legacy wide schema."""
    if df is None or df.empty or "bank" not in df.columns:
        return None

    # VNStock v5: period/year | id | name | ... | value
    period_column = "period" if "period" in df.columns else ("year" if "year" in df.columns else None)
    if period_column is not None and "value" in df.columns:
        id_column = "id" if "id" in df.columns else ("item_id" if "item_id" in df.columns else None)
        if id_column is None:
            return None
        periods = pd.to_numeric(df[period_column], errors="coerce")
        hit = df[(df["bank"] == bank) & (df[id_column] == item_id) & (periods == int(year))].copy()
        if hit.empty:
            return None
        values = pd.to_numeric(hit["value"], errors="coerce").dropna()
        return float(values.iloc[-1]) if not values.empty else None

    # Legacy wide schema
    id_column = "item_id" if "item_id" in df.columns else ("id" if "id" in df.columns else None)
    if id_column is None or str(year) not in df.columns:
        return None
    hit = df[(df["bank"] == bank) & (df[id_column] == item_id)].copy()
    if hit.empty:
        return None
    values = pd.to_numeric(hit[str(year)], errors="coerce").dropna()
    return float(values.iloc[-1]) if not values.empty else None

def add_financial_clean_data(credit_clean, raw_balance, raw_income, financial_sources):
    result = credit_clean.copy()
    rows = []

    raw_specs = {
        "total_assets": (raw_balance, "BS_TOTAL_ASSETS", "Tổng tài sản"),
        "equity": (raw_balance, "BS_EQUITY", "Vốn chủ sở hữu"),
        "customer_deposits": (raw_balance, "deposits_from_customers", "Tiền gửi khách hàng"),
        "total_liabilities": (raw_balance, "BS_TOTAL_LIABILITIES", "Tổng nợ phải trả"),
        "net_profit": (raw_income, "IS_NET_PROFIT_AFTER_TAX", "Lợi nhuận sau thuế"),
        "operating_expenses": (raw_income, "operating_expenses", "Chi phí hoạt động"),
    }

    income_components = [
        "IS_NET_INTEREST_INCOME",
        "IS_NET_FEE_AND_COMMISSION_INCOME",
        "IS_NET_GAIN_LOSS_FROM_FOREIGN_CURRENCIES_AND_GOLD_TRADING",
        "IS_NET_GAIN_LOSS_FROM_TRADING_SECURITIES",
        "IS_NET_GAIN_LOSS_FROM_INVESTMENT_SECURITIES",
        "IS_NET_OTHER_INCOME",
    ]

    for bank, ticker in BANKS.items():
        for year, variables in FINANCIAL_REQUIRED.items():
            for variable in variables:
                if variable in {"casa", "nim"}:
                    indicator = variable.upper()
                    hit = financial_sources[
                        (financial_sources["bank"] == bank)
                        & (financial_sources["year"] == year)
                        & (financial_sources["indicator"] == indicator)
                    ]
                    if hit.empty:
                        value = None
                        title = url = None
                        status = "missing"
                    else:
                        src = hit.iloc[0]
                        value = src["value"]
                        title = src["source_title"]
                        url = src["source_url"]
                        status = src["status"]
                    rows.append({
                        "bank": bank, "ticker": ticker, "year": year,
                        "variable": variable, "value_clean": value, "unit_clean": "%",
                        "source": "Official disclosure / annual report",
                        "source_title": title, "source_url": url,
                        "evidence_text": f"{indicator} FY2025 = {value}%" if value is not None else None,
                        "status": status,
                    })
                    continue

                detail_supplement = DETAIL_SUPPLEMENTS.get(bank, {}).get((year, variable))
                if detail_supplement is not None:
                    title, url = CREDIT_SUPPLEMENT_SOURCES[bank]["debt"]
                    rows.append({
                        "bank": bank, "ticker": ticker, "year": year,
                        "variable": variable, "value_clean": detail_supplement, "unit_clean": "ty_dong",
                        "source": "Official audited report supplement",
                        "source_title": title, "source_url": url,
                        "evidence_text": f"Audited-report detail supplement; variable={variable}; value={detail_supplement} ty_dong",
                        "status": "verified_supplement",
                    })
                    continue

                if variable == "total_operating_income":
                    values = [raw_value(raw_income, bank, item_id, year) for item_id in income_components]
                    value_vnd = sum(values) if all(v is not None for v in values) else None
                    value = value_vnd / 1_000_000_000 if value_vnd is not None else None
                    rows.append({
                        "bank": bank, "ticker": ticker, "year": year,
                        "variable": variable, "value_clean": value, "unit_clean": "ty_dong",
                        "source": "Calculated from VNStock",
                        "source_title": "VNStock - Báo cáo kết quả hoạt động kinh doanh",
                        "source_url": None,
                        "evidence_text": "Tổng thu nhập hoạt động = NII + thuần DV + FX + CK kinh doanh + CK đầu tư + HĐ khác + góp vốn",
                        "status": "verified_calculated" if value is not None else "missing",
                    })
                    continue

                df, item_id, label = raw_specs[variable]
                value_vnd = raw_value(df, bank, item_id, year)
                value = value_vnd / 1_000_000_000 if value_vnd is not None else None
                rows.append({
                    "bank": bank, "ticker": ticker, "year": year,
                    "variable": variable, "value_clean": value, "unit_clean": "ty_dong",
                    "source": "VNStock",
                    "source_title": f"VNStock - {label}",
                    "source_url": None,
                    "evidence_text": f"item_id={item_id}; target_year={year}; raw_unit=VND; clean_unit=ty_dong",
                    "status": "verified" if value is not None else "missing",
                })

    if rows:
        result = pd.concat([result, pd.DataFrame(rows)], ignore_index=True, sort=False)

    return result.sort_values(["bank", "year", "variable"]).reset_index(drop=True)


def calculate_financial_metrics(clean, credit_metrics):
    rows = []
    for bank, ticker in BANKS.items():
        assets_2024 = one_value(clean, bank, 2024, "total_assets")
        assets_2025 = one_value(clean, bank, 2025, "total_assets")
        equity_2024 = one_value(clean, bank, 2024, "equity")
        equity_2025 = one_value(clean, bank, 2025, "equity")
        deposits_2025 = one_value(clean, bank, 2025, "customer_deposits")
        liabilities_2025 = one_value(clean, bank, 2025, "total_liabilities")
        net_profit_2025 = one_value(clean, bank, 2025, "net_profit")
        opex_2025 = one_value(clean, bank, 2025, "operating_expenses")
        total_operating_income = one_value(clean, bank, 2025, "total_operating_income")
        casa = one_value(clean, bank, 2025, "casa")
        nim = one_value(clean, bank, 2025, "nim")

        average_assets = ((assets_2024 + assets_2025) / 2
                          if assets_2024 is not None and assets_2025 is not None else None)
        average_equity = ((equity_2024 + equity_2025) / 2
                          if equity_2024 is not None and equity_2025 is not None else None)

        credit_row = credit_metrics[credit_metrics["bank"] == bank]
        credit = credit_row.iloc[0].to_dict() if not credit_row.empty else {}

        rows.append({
            "bank": bank, "ticker": ticker, "year": 2025,
            "NPL_%": credit.get("NPL_%"),
            "Group2_%": credit.get("Group2_%"),
            "LLR_NPL_%": credit.get("LLR_NPL_%"),
            "CoR_%": credit.get("CoR_%"),
            "CAR_%": credit.get("CAR_%"),
            "Equity_Assets_%": safe_pct(equity_2025, assets_2025),
            "CASA_%": casa,
            "Customer_Deposits_Liabilities_%": safe_pct(deposits_2025, liabilities_2025),
            "ROA_%": safe_pct(net_profit_2025, average_assets),
            "ROE_%": safe_pct(net_profit_2025, average_equity),
            "NIM_%": nim,
            "CIR_%": safe_pct(abs(opex_2025) if opex_2025 is not None else None, total_operating_income),
        })

    return pd.DataFrame(rows)

def create_financial_sources():
    rows = []
    casa_title, casa_url = FINANCIAL_RATIO_SOURCES["casa"]
    for bank, ticker in BANKS.items():
        rows.append({
            "bank": bank, "ticker": ticker, "year": 2025, "indicator": "CASA",
            "value": FINANCIAL_RATIO_SUPPLEMENTS_2025[bank]["casa"], "unit": "%",
            "source_title": casa_title, "source_url": casa_url, "status": "verified_supplement",
        })
        nim_title, nim_url = FINANCIAL_RATIO_SOURCES["nim"][bank]
        rows.append({
            "bank": bank, "ticker": ticker, "year": 2025, "indicator": "NIM",
            "value": FINANCIAL_RATIO_SUPPLEMENTS_2025[bank]["nim"], "unit": "%",
            "source_title": nim_title, "source_url": nim_url, "status": "verified_supplement",
        })
    return pd.DataFrame(rows)


# ============================================================
# 6. QUALITY CHECKS + SOURCES
# ============================================================

def create_missing_check(credit_clean):
    missing = credit_clean[
        credit_clean["value_clean"].isna()
    ].copy()

    columns = [
        "bank", "year", "variable",
        "status", "source", "evidence_text",
    ]

    if missing.empty:
        return pd.DataFrame(columns=columns)

    return missing[columns].reset_index(drop=True)


def create_consistency_check(credit_clean, metrics):
    issues = []

    for _, row in credit_clean.iterrows():
        if pd.isna(row["value_clean"]):
            continue

        expected_unit = "%" if row["variable"] in {"car", "casa", "nim"} else "ty_dong"

        if row["unit_clean"] != expected_unit:
            issues.append({
                "bank": row["bank"],
                "year": row["year"],
                "item": row["variable"],
                "check": "unit",
                "status": "review",
                "detail": f"Expected {expected_unit}, got {row['unit_clean']}",
            })

        if row["variable"] not in {"car", "casa", "nim"} and float(row["value_clean"]) < 0:
            issues.append({
                "bank": row["bank"],
                "year": row["year"],
                "item": row["variable"],
                "check": "sign",
                "status": "review",
                "detail": "Negative value",
            })

    for _, row in metrics.iterrows():
        for column in ["NPL_%", "Group2_%", "CAR_%"]:
            value = row[column]
            if pd.notna(value) and not 0 <= float(value) <= 100:
                issues.append({
                    "bank": row["bank"],
                    "year": 2025,
                    "item": column,
                    "check": "range",
                    "status": "review",
                    "detail": f"Out of 0-100: {value}",
                })

    columns = [
        "bank", "year", "item",
        "check", "status", "detail",
    ]

    if not issues:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(issues, columns=columns)


def create_data_sources(credit_clean):
    columns = [
        "bank", "year", "variable",
        "value_clean", "unit_clean",
        "source", "source_title", "source_url",
        "evidence_text", "status",
    ]

    result = credit_clean.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = None

    return result[columns].copy()


def metric_definitions():
    return pd.DataFrame([
        {"indicator": "NPL", "formula": "(Group 3 + Group 4 + Group 5) / Total classified loans (Groups 1-5) * 100", "unit": "%", "direction": "LOW", "weight_BCDS": "14%"},
        {"indicator": "Group 2 Ratio", "formula": "Group 2 / Total classified loans (Groups 1-5) * 100", "unit": "%", "direction": "LOW", "weight_BCDS": "7%"},
        {"indicator": "LLR/NPL", "formula": "Credit risk provision / NPL amount * 100", "unit": "%", "direction": "HIGH", "weight_BCDS": "8%"},
        {"indicator": "CoR", "formula": "Provision expense / Average loans(2024, 2025) * 100", "unit": "%", "direction": "LOW", "weight_BCDS": "6%"},
        {"indicator": "CAR", "formula": "Official disclosed CAR at year-end 2025", "unit": "%", "direction": "HIGH", "weight_BCDS": "7%"},
        {"indicator": "Equity / Total Assets", "formula": "Equity at year-end 2025 / Total assets at year-end 2025 * 100", "unit": "%", "direction": "HIGH", "weight_BCDS": "5%"},
        {"indicator": "CASA", "formula": "Demand deposits / Customer deposits * 100; use official/comparable disclosed FY2025 ratio", "unit": "%", "direction": "HIGH", "weight_BCDS": "4%"},
        {"indicator": "Customer Deposits / Total Liabilities", "formula": "Customer deposits / Total liabilities * 100", "unit": "%", "direction": "HIGH", "weight_BCDS": "4%"},
        {"indicator": "ROA", "formula": "Net profit 2025 / Average total assets(2024, 2025) * 100", "unit": "%", "direction": "HIGH", "weight_BCDS": "5%"},
        {"indicator": "ROE", "formula": "Net profit 2025 / Average equity(2024, 2025) * 100", "unit": "%", "direction": "HIGH", "weight_BCDS": "5%"},
        {"indicator": "NIM", "formula": "Net interest income / Average interest-earning assets * 100; prefer official FY2025 disclosure", "unit": "%", "direction": "HIGH", "weight_BCDS": "5%"},
        {"indicator": "CIR", "formula": "Operating expenses / Total operating income * 100", "unit": "%", "direction": "LOW", "weight_BCDS": "5%"},
    ])


# ============================================================
# 7. MAIN
# ============================================================

def main():
    print_environment()
    Fundamental = load_vnstock()

    balance_frames = []
    income_frames = []
    status_rows = []

    print("\n" + "=" * 70)
    print("CRAWL VNSTOCK - 5 BANKS")
    print("=" * 70)

    for bank, ticker in BANKS.items():
        try:
            data = crawl_bank(
                Fundamental, bank, ticker
            )

            balance_frames.append(
                data["balance_sheet"]
            )
            income_frames.append(
                data["income_statement"]
            )

            success = (
                not data["balance_sheet"].empty
                or not data["income_statement"].empty
            )

            status_rows.append({
                "bank": bank,
                "ticker": ticker,
                "source": "VNStock",
                "status": "success" if success else "review",
                "message": "",
            })

        except Exception as error:
            print(f"[ERROR] {bank}: {error}")
            status_rows.append({
                "bank": bank,
                "ticker": ticker,
                "source": "VNStock",
                "status": "error",
                "message": str(error),
            })

    # Giữ bản crawl gốc để extraction dùng đúng source field của VNStock.
    raw_balance_source = combine_frames(balance_frames)
    raw_income_source = combine_frames(income_frames)

    # Raw sheets để nộp: toàn bộ khoản mục, nhưng chỉ 2024-2025
    # và nhãn năm đã được chuẩn hóa theo năm thực tế.
    raw_balance = normalize_raw_years(raw_balance_source)
    raw_income = normalize_raw_years(raw_income_source)

    clean = create_clean_vnstock_data(
        raw_balance_source, raw_income_source
    )
    clean = add_credit_supplements(clean)

    credit_clean = create_credit_clean_data(clean)
    financial_sources = create_financial_sources()
    model_clean = add_financial_clean_data(
        credit_clean, raw_balance, raw_income, financial_sources
    )
    credit_metrics = calculate_credit_metrics(model_clean)
    financial_metrics = calculate_financial_metrics(model_clean, credit_metrics)
    missing_check = create_missing_check(model_clean)
    consistency_check = create_consistency_check(
        model_clean, financial_metrics
    )
    data_sources = create_data_sources(model_clean)
    crawl_status = pd.DataFrame(status_rows)

    model_clean.to_csv(
        CLEAN_CSV_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl",
    ) as writer:
        raw_balance.to_excel(
            writer, sheet_name="Raw_Balance", index=False
        )
        raw_income.to_excel(
            writer, sheet_name="Raw_Income", index=False
        )
        model_clean.to_excel(
            writer, sheet_name="Clean_Data", index=False
        )
        financial_metrics.to_excel(
            writer, sheet_name="BCDS_Metrics", index=False
        )
        financial_sources.to_excel(
            writer, sheet_name="Financial_Sources", index=False
        )
        missing_check.to_excel(
            writer, sheet_name="Missing_Check", index=False
        )
        consistency_check.to_excel(
            writer, sheet_name="Consistency_Check", index=False
        )
        data_sources.to_excel(
            writer, sheet_name="Data_Sources", index=False
        )
        metric_definitions().to_excel(
            writer, sheet_name="Metric_Definitions", index=False
        )
        crawl_status.to_excel(
            writer, sheet_name="Crawl_Status", index=False
        )

    print("\n" + "=" * 70)
    print("HOÀN THÀNH")
    print("=" * 70)
    print(f"Clean input rows     : {len(model_clean)}")
    print(f"Missing inputs       : {len(missing_check)}")
    print(f"Consistency issues   : {len(consistency_check)}")
    print(f"Excel                : {OUTPUT_FILE}")
    print(f"CSV                  : {CLEAN_CSV_FILE}")
    print("\nBCDS financial metrics (1-12):")
    print(financial_metrics.to_string(index=False))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[STOP] Đã dừng chương trình.")
    except PermissionError:
        print(
            "\n[ERROR] Không thể ghi file output. "
            "Hãy đóng credit_data.xlsx nếu đang mở rồi chạy lại."
        )
        raise
    except Exception as error:
        print(f"\n[ERROR] {error}")
        raise
