# BCDS 2025 — Streamlit dashboard

Giao diện đã được thiết kế lại theo ảnh tham chiếu. Xem
[`review_artifacts/redesign_report.md`](review_artifacts/redesign_report.md)
để đọc kết quả kiểm tra, đường dẫn ảnh chụp và các khác biệt còn lại.

Frontend đọc các output có sẵn của project. Không import backend, không chạy
pipeline/scoring, không ghi vào CSV/JSON/XLSX. Mọi thay đổi nằm trong `dashboard/`.

Chạy từ repo Git `Credit-assessmen-git`, branch `feat/dashboard`:

```powershell
py -m venv '.\dashboard\.venv'
& '.\dashboard\.venv\Scripts\python.exe' -X utf8 -m pip install -r '.\dashboard\requirements-dev.txt'
& '.\dashboard\.venv\Scripts\python.exe' -m streamlit run '.\dashboard\app.py'
```

Data paths được resolve theo vị trí app, không theo working directory. Nút
**Làm mới dữ liệu** chỉ xóa cache và đọc lại các output. Cache cũng tự đổi khi
thời gian sửa hoặc kích thước file đổi, ở lần tương tác/rerun kế tiếp.

## Kiểm tra frontend

```powershell
& '.\dashboard\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s '.\dashboard\tests' -p 'test_*.py' -v
```

Từ project root bên trong, kiểm tra parity/hash và chụp ảnh bằng Edge headless
(Streamlit cần đang chạy khi chụp ảnh):

```powershell
& '.\dashboard\.venv\Scripts\python.exe' -X utf8 dashboard/tests/validate_recovery.py
& '.\dashboard\.venv\Scripts\python.exe' -X utf8 dashboard/tests/browser_review.py --url http://127.0.0.1:8501
```

Kết quả khôi phục phiên làm việc được ghi trong
[`review_artifacts/recovery_report.md`](review_artifacts/recovery_report.md).
`protected_baseline.json` là baseline được tìm thấy từ phiên trước;
`recovery_checkpoint.json` ghi trạng thái lúc tiếp tục. Công cụ validation so
sánh cả hai với hash hiện tại, không ghi đè baseline gốc.

Test fault cases sử dụng bản sao tạm thời, không thay đổi file nguồn.
Browser automation là công cụ development tùy chọn, được tách trong
`requirements-dev.txt`. Ảnh và kết quả kiểm tra ở `review_artifacts/`.

## Nguồn của năm trang

| Trang | File đọc |
|---|---|
| Tổng quan | ranking, group scores, criterion scores, scoring metadata |
| So sánh | ranking, group scores |
| Chi tiết tiêu chí | criterion scores; workbook Metric_Definitions; merged dataset khi được chọn |
| D1–D3 | digital dataset, digital evidence |
| Nguồn & phương pháp | credit_data_clean, digital evidence, scoring metadata, group scores; các sheet Excel khi được chọn |

Điểm nhóm so sánh dùng `group_score_100`; điểm đóng góp dùng `group_score`
và `group_max` đã xuất. Giá trị `normalized_0_1` giữ thang 0–1.
Không tính lại điểm hay xếp hạng. NA được trình bày là N/A, không thay bằng 0.
Tên ngân hàng giữ cách viết từ từng nguồn; ticker là định danh.

`review`/`provisional_review` chỉ hiển thị tại **Nguồn dữ liệu & phương pháp**,
bao gồm badge kết quả và trạng thái bằng chứng. Các trang phân tích ẩn badge,
cột review và ghi chú rà soát ở lớp trình bày; dữ liệu gốc không bị thay đổi.
Trường legacy `included_in_BCDS_15` không điều khiển scoring hoặc UI.
D1–D3 thuộc mô hình 12 + 3 hiện tại. Không tự tạo rubric cấp độ 0–3.

Nếu file hoặc schema bị lỗi, component liên quan hiện cảnh báo. Các nguồn độc
lập khác vẫn hoạt động. Workbook chỉ được đọc ở trang có nhu cầu và được cache.
