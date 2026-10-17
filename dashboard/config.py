"""Presentation constants only: no model weights, scores or ranking."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
YEAR = 2025
BANKS = ("VCB", "BID", "CTG", "TCB", "MBB")
DIGITAL_CODES = ("D1", "D2", "D3")
PAGES = (
    "Tổng quan", "So sánh ngân hàng", "Chi tiết tiêu chí",
    "Chuyển đổi số D1–D3", "Nguồn dữ liệu & phương pháp",
)
BANK_COLORS = {
    "VCB": "#14938d", "BID": "#345da3", "CTG": "#417ee0",
    "TCB": "#e35c76", "MBB": "#8060cd",
}
GROUP_ORDER = ("credit", "capital", "profitability", "digital")
GROUP_LABELS = {
    "credit": "Chất lượng tín dụng", "capital": "Vốn và nguồn vốn",
    "profitability": "Sinh lời và hiệu quả", "digital": "Chuyển đổi số",
}
CRITERION_LABELS = {
    "NPL": "Tỷ lệ nợ xấu", "Group2": "Tỷ lệ nợ nhóm 2",
    "LLR": "Tỷ lệ bao phủ nợ xấu", "CoR": "Chi phí rủi ro tín dụng",
    "CAR": "Tỷ lệ an toàn vốn", "EquityAssets": "Vốn chủ sở hữu / Tổng tài sản",
    "CASA": "Tỷ lệ tiền gửi không kỳ hạn",
    "DepositsLiabilities": "Tiền gửi khách hàng / Tổng nợ phải trả",
    "ROA": "Sinh lời trên tài sản", "ROE": "Sinh lời trên vốn chủ sở hữu",
    "NIM": "Biên lãi thuần", "CIR": "Chi phí / Thu nhập",
    "D1": "Định danh & onboarding", "D2": "Quy trình tín dụng / cho vay",
    "D3": "AI / Big Data / ML trong tín dụng & quản trị rủi ro",
}
# Match existing workbook labels; these aliases affect explanation only.
DEFINITION_ALIASES = {
    "Group2": "Group 2 Ratio", "LLR": "LLR/NPL",
    "EquityAssets": "Equity / Total Assets",
    "DepositsLiabilities": "Customer Deposits / Total Liabilities",
}
STATUS_LABELS = {
    "verified": "Đã xác thực", "review": "Đang rà soát",
    "missing": "Thiếu dữ liệu", "provided": "Dữ liệu được cung cấp",
    "verified_supplement": "Đã xác thực — bổ sung",
    "provisional_review": "Kết quả tạm thời — đang rà soát",
    "incomplete": "Chưa đầy đủ", "success": "Thành công",
}
DIRECTION_LABELS = {
    "low": "Thấp hơn tốt hơn", "high": "Cao hơn tốt hơn",
    "fixed": "Đánh giá định tính · thang 0–3",
}
