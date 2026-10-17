"""Run: python -m streamlit run dashboard/app.py. Read-only presentation."""
from pathlib import Path
import sys

# Support Streamlit, AppTest and launch commands from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

import charts
import data_adapter as data
import ui_components as ui
from config import (
    CRITERION_LABELS, DEFINITION_ALIASES, DIGITAL_CODES, DIRECTION_LABELS,
    GROUP_ORDER, PAGES, YEAR,
)

st.set_page_config(page_title="BCDS 2025 · Phân tích ngân hàng", page_icon="▥", layout="wide", initial_sidebar_state="expanded")
ui.html("<style>" + Path(__file__).with_name("styles.css").read_text(encoding="utf-8")
        + ui.bank_selector_logo_css() + "</style>")

LABELS = {
    "bank": "Ngân hàng", "ticker": "Mã", "year": "Năm", "rank": "Hạng",
    "criterion": "Tiêu chí", "group": "Mã nhóm", "group_label": "Nhóm",
    "raw_value": "Giá trị gốc", "normalized_0_1": "Chuẩn hóa (0–1)",
    "base_weight": "Trọng số gốc (điểm)", "effective_weight": "Trọng số hiệu lực (điểm)",
    "weighted_score": "Điểm đóng góp", "direction": "Chiều đánh giá", "status": "Trạng thái",
    "total_score": "Tổng điểm", "group_score": "Điểm đóng góp nhóm", "group_max": "Tối đa nhóm",
    "group_score_100": "Điểm nhóm (0–100)", "variable": "Biến", "value_clean": "Giá trị",
    "unit_clean": "Đơn vị", "source": "Nguồn", "source_title": "Tên tài liệu",
    "source_url": "Tài liệu nguồn", "evidence_text": "Bằng chứng", "bank_code": "Mã",
    "bank_name": "Ngân hàng", "indicator_code": "Tiêu chí", "indicator_name": "Nội dung đánh giá",
    "score_0_3": "Điểm (0–3)", "score_100": "Điểm (0–100)", "source_description": "Mô tả nguồn",
    "source_type": "Loại nguồn", "page_or_section": "Trang / Mục", "note": "Ghi chú", "as_of": "Thời điểm",
}


def load(loader, **kwargs):
    try:
        return loader(**kwargs)
    except data.DataIssue as exc:
        st.warning(str(exc))
        return None


def plot(figure, key):
    st.plotly_chart(
        figure,
        width="stretch",
        config={"displayModeBar": False, "responsive": True},
        key=key,
    )


def remember_bank(widget_key):
    st.session_state["selected_bank"] = st.session_state[widget_key]


def bank_picker(frame, key, bank_column="ticker", name_column="bank"):
    options = frame[bank_column].drop_duplicates().tolist()
    names = frame.drop_duplicates(bank_column).set_index(bank_column)[name_column].to_dict()
    selected = st.session_state.get("selected_bank", options[0])
    if selected not in options:
        selected = options[0]
    return st.selectbox("Ngân hàng", options, index=options.index(selected),
                        format_func=lambda t: f"{t} · {names[t]}", key=key,
                        on_change=remember_bank, args=(key,))


def group_order(frame):
    order = {g: i for i, g in enumerate(GROUP_ORDER)}
    return frame.sort_values("group", key=lambda values: values.map(order).fillna(len(order)), kind="stable")


def ranking_status(ranking):
    if "score_status" in ranking:
        badges = " ".join(ui.status_badge(v, show_review=True) for v in ranking.score_status.drop_duplicates())
        ui.html('<div class="ranking-status">' + badges + '</div>')


def criterion_units(definitions):
    units = {code: "điểm" for code in DIGITAL_CODES}
    if definitions is None or not {"indicator", "unit"}.issubset(definitions.columns):
        return units
    aliases = {definition: code for code, definition in DEFINITION_ALIASES.items()}
    for record in definitions[["indicator", "unit"]].dropna(subset=["indicator"]).to_dict("records"):
        code = aliases.get(record["indicator"], record["indicator"])
        unit = str(record["unit"]).strip()
        units[code] = unit if unit else "—"
    return units


def overview():
    ui.page_header("Chấm điểm tín dụng ngân hàng tích hợp chuyển đổi số",
                   "Mô hình 12 tiêu chí định lượng + 3 tiêu chí định tính", PAGES[0], overview=True)
    ranking = load(data.load_ranking)
    criteria = load(data.load_criterion_scores)
    metadata = load(data.load_scoring_metadata)
    quantitative = criteria.loc[~criteria.criterion.isin(DIGITAL_CODES), "criterion"].nunique() if criteria is not None else None
    qualitative = criteria.loc[criteria.criterion.isin(DIGITAL_CODES), "criterion"].nunique() if criteria is not None else None
    leaders = ranking.loc[ranking["rank"].eq(ranking["rank"].min())] if ranking is not None else None
    leader = " · ".join(leaders.ticker) if leaders is not None else "N/A"
    ui.metrics([
        ("Ngân hàng", ranking.ticker.nunique() if ranking is not None else "N/A", "Phạm vi nghiên cứu"),
        ("Tiêu chí", metadata.get("criteria_count", "N/A") if metadata else "N/A", "Mô hình đánh giá"),
        ("Định lượng", quantitative, "Chỉ tiêu tài chính"),
        ("Định tính", qualitative, "Chuyển đổi số D1–D3"),
        ("Dẫn đầu", leader, "Theo thứ hạng đã xuất"),
        ("Điểm cao nhất", ui.number(ranking.total_score.max()) if ranking is not None else "N/A", "Thang điểm 100"),
    ])
    if ranking is not None:
        left, right = st.columns([1, 1.04], gap="medium")
        with left, ui.panel("overview_table"):
            ui.section_header("Bảng xếp hạng ngân hàng", "Kết quả tổng hợp từ mô hình của nhóm", "trophy", "gold")
            ui.ranking_table(ranking)
        with right, ui.panel("overview_bar"):
            ui.section_header("Điểm tổng hợp ngân hàng", "So sánh trên thang 0–100", "bars")
            figure = charts.logo_ranking_bar(ranking, 220, overview=True)
            with st.container(key="overview_totals_chart"):
                logo_column, chart_column = st.columns([1, 14], gap=None)
                with logo_column:
                    ui.bank_logo_axis(figure.data[0].y, height=figure.layout.height,
                                      top=figure.layout.margin.t, bottom=figure.layout.margin.b)
                with chart_column:
                    plot(figure, "overview_ranking")
    groups = load(data.load_group_scores)
    if groups is not None:
        with ui.panel("overview_groups"):
            ui.section_header("Bốn góc nhìn về ngân hàng", "Điểm nhóm trên thang 100 · trọng số nhóm được trình bày riêng trong phương pháp", "shield", "teal")
            tickers = ranking.sort_values("rank").ticker.tolist() if ranking is not None else groups.ticker.drop_duplicates().tolist()
            mini_columns = st.columns(4, gap="small")
            for index, (column, group) in enumerate(zip(mini_columns, GROUP_ORDER)):
                part = groups.loc[groups.group.eq(group)]
                with column, st.container(key="group_mini_" + group):
                    if part.empty:
                        st.info("Nhóm chưa có dữ liệu.")
                        continue
                    ui.section_header(part.group_label.iloc[0], symbol=("shield", "coins", "bars", "screen")[index], tone=("blue", "gold", "violet", "blue")[index])
                    plot(charts.group_mini(part, tickers), "overview_group_" + group)
                    ui.bank_identity_strip(tickers, compact=True)
        with ui.panel("overview_insights"):
            ui.section_header("Nhận định nổi bật", "Dựa trên kết quả dữ liệu hiện tại", "bulb", "gold")
            ui.insight_cards(group_order(groups))


def comparison():
    ui.page_header("So sánh ngân hàng", "Đối chiếu điểm tổng hợp, bốn nhóm tiêu chí và thế mạnh tương đối.", PAGES[1])
    ranking = load(data.load_ranking)
    groups = load(data.load_group_scores)
    if ranking is None:
        return
    ranking = ranking.sort_values("rank", kind="stable")
    options = ranking.ticker.tolist()
    with ui.panel("comparison_filter"):
        selected = st.multiselect("Chọn từ 2 đến 5 ngân hàng", options, default=options,
                                  max_selections=5, key="comparison_banks")
    if len(selected) < 2:
        st.info("Vui lòng chọn ít nhất 2 ngân hàng để so sánh.")
        return
    chosen = ranking.loc[ranking.ticker.isin(selected)]
    selected_groups = groups.loc[groups.ticker.isin(selected)] if groups is not None else None
    ui.bank_mini_cards(chosen, selected_groups)
    left, right = st.columns([1.2, 1], gap="medium")
    if groups is not None:
        with left, ui.panel("comparison_groups"):
            ui.section_header("So sánh theo nhóm tiêu chí", "Bốn nhóm · cùng thang điểm 100", "bars")
            plot(charts.group_comparison(selected_groups, chosen.ticker.tolist()), "compare_groups")
    with right, ui.panel("comparison_totals"):
        ui.section_header("So sánh tổng điểm", "Thứ tự theo xếp hạng đã xuất", "trophy", "gold")
        figure = charts.comparison_ranking_bar(chosen)
        with st.container(key="comparison_totals_chart"):
            logo_column, chart_column = st.columns([1, 14], gap=None)
            with logo_column:
                ui.bank_logo_axis(figure.data[0].y, height=figure.layout.height,
                                  top=figure.layout.margin.t, bottom=figure.layout.margin.b)
            with chart_column:
                plot(figure, "compare_totals")
    if groups is not None:
        left, right = st.columns([1.65, 1], gap="medium")
        with left, ui.panel("comparison_matrix"):
            ui.section_header("Ma trận so sánh", "Bốn dòng đầu là điểm nhóm / 100; dòng cuối là tổng điểm đã xuất", "layers", "teal")
            matrix = group_order(groups.loc[groups.ticker.isin(selected)]).pivot(index="group_label", columns="ticker", values="group_score_100")
            order = group_order(groups).group_label.drop_duplicates().tolist()
            matrix = matrix.reindex(index=order, columns=chosen.ticker)
            matrix.loc["Tổng điểm"] = chosen.set_index("ticker").total_score
            ui.comparison_matrix_table(matrix, chosen)
            with st.container(key="comparison_matrix_native"):
                ui.data_table(matrix.rename_axis("Nhóm").reset_index(), formats={t: "%.2f" for t in chosen.ticker}, key="comparison_matrix")
        with right, ui.panel("comparison_summary"):
            ui.section_header("Nhận định ngân hàng đã chọn", "Giải nguyên các trường hợp động điểm", "bulb", "gold")
            ui.analytical_summary(chosen, selected_groups)


def criterion_detail():
    ui.page_header("Chi tiết tiêu chí", "Theo dõi giá trị gốc, điểm chuẩn hóa, trọng số và đóng góp đã được xuất.", PAGES[2])
    criteria = load(data.load_criterion_scores)
    if criteria is None:
        return
    definitions = load(data.load_workbook_sheet, sheet="Metric_Definitions")
    units = criterion_units(definitions)
    with ui.panel("criterion_filter"):
        a, b, c, d = st.columns([1, 1.15, .85, 1.4], gap="medium")
        with a:
            ticker = bank_picker(criteria, "criterion_bank")
        with b:
            groups = group_order(criteria).drop_duplicates("group").set_index("group").group_label.to_dict()
            group = st.selectbox("Nhóm tiêu chí", [None] + list(groups), format_func=lambda v: "Tất cả nhóm" if v is None else groups[v], key="criterion_group")
        with c:
            kind = st.selectbox("Loại tiêu chí", ["Tất cả", "Định lượng", "Định tính"], key="criterion_kind")
        filtered = data.filter_criteria(criteria, ticker, group, kind)
        with d:
            codes = filtered.criterion.tolist()
            if st.session_state.get("criterion_selected") not in codes:
                st.session_state["criterion_selected"] = codes[0] if codes else None
            code = st.selectbox("Tiêu chí cần xem", codes, format_func=lambda v: f"{v} · {CRITERION_LABELS.get(v, v)}", key="criterion_selected", disabled=filtered.empty, placeholder="Không có tiêu chí phù hợp")
    if filtered.empty:
        st.info("Không có tiêu chí phù hợp với bộ lọc hiện tại. Hãy đổi nhóm hoặc loại tiêu chí.")
        return
    left, right = st.columns([2.65, 1], gap="medium")
    with left, ui.panel("criterion_results"):
        ui.section_header(f"Danh sách tiêu chí · {ticker}", f"{len(filtered)} tiêu chí phù hợp · chuẩn hóa thang 0–1", "file")
        search = st.text_input("Tìm kiếm tiêu chí", key="criterion_search", placeholder="Tìm theo mã hoặc tên tiêu chí")
        visible = filtered.loc[
            filtered.criterion.str.contains(search, case=False, na=False)
            | filtered.criterion.map(lambda value: CRITERION_LABELS.get(value, value)).str.contains(search, case=False, na=False)
        ] if search else filtered
        columns = ["criterion", "group_label", "raw_value", "normalized_0_1", "effective_weight", "weighted_score", "status"]
        if st.checkbox("Hiển thị trọng số gốc và chiều đánh giá", key="criterion_extra_columns"):
            columns += ["base_weight", "direction"]
        display = visible[[c for c in columns if c in visible]].copy()
        if "direction" in display:
            display["direction"] = display.direction.map(lambda v: DIRECTION_LABELS.get(v, v))
        compact_labels = {**LABELS, "normalized_0_1": "Chuẩn hóa (0–1)", "effective_weight": "Trọng số", "weighted_score": "Đóng góp"}
        ui.criterion_table(visible, units, code)
        with st.container(key="criterion_table_native"):
            ui.data_table(display, compact_labels, {"raw_value": "%.2f", "normalized_0_1": "%.2f", "base_weight": "%.2f", "effective_weight": "%.2f", "weighted_score": "%.2f"}, height=min(528, 38 + len(display) * 32), key="criterion_table")
    row = filtered.loc[filtered.criterion.eq(code)].iloc[0]
    with right, ui.panel("criterion_detail"):
        ui.section_header("Chi tiết tiêu chí", ticker, "layers", "violet")
        bank_name = filtered.loc[filtered.ticker.eq(ticker), "bank"].iloc[0]
        ui.html(f'<div class="criterion-bank-name">{ui.safe(ticker)} · {ui.safe(bank_name)}</div>')
        ui.criterion_detail_card(row, units, bank_name)
    with ui.panel("criterion_chart"):
        chart_mode = st.selectbox("Hiển thị biểu đồ", ["Chuẩn hóa (0–1)", "Giá trị gốc"], key="criterion_chart_mode")
        mode = "raw" if chart_mode == "Giá trị gốc" else "normalized"
        ui.section_header(f"{code} · So sánh giữa các ngân hàng",
                          f"So sánh {('giá trị gốc' if mode == 'raw' else 'điểm chuẩn hóa')} của tiêu chí {code} (đơn vị: {units.get(code, '—')})",
                          "bars")
        plot(charts.criterion_comparison(criteria, code, mode=mode), "criterion_comparison")
    with st.expander("Giải thích tiêu chí và ngữ cảnh dữ liệu"):
        if code in DIGITAL_CODES:
            st.write("Đánh giá định tính trên thang 0–3, dựa trên bằng chứng. Điểm do upstream cung cấp; Dashboard chỉ hiển thị kết quả.")
        else:
            if definitions is not None and {"indicator", "formula", "unit"}.issubset(definitions.columns):
                definition = definitions.loc[definitions.indicator.eq(DEFINITION_ALIASES.get(code, code))]
                if not definition.empty:
                    st.write("Đơn vị: " + ui.text(definition.iloc[0]["unit"]))
                    st.write("Công thức tham chiếu từ dự án: " + ui.text(definition.iloc[0]["formula"]))
                    st.caption("Công thức chỉ phục vụ giải thích. Dashboard không tính lại giá trị hay điểm.")
        if st.checkbox("Hiển thị dòng dữ liệu hợp nhất", key="show_merged"):
            merged = load(data.load_merged_data)
            if merged is not None:
                # Legacy inclusion metadata is not used to select criteria or scores.
                contextual = data.select_bank(merged, ticker).drop(columns=["included_in_BCDS_15"], errors="ignore")
                ui.data_table(contextual, LABELS, key="merged_context")


def digital():
    ui.page_header("Chuyển đổi số D1–D3", "Từ định danh số đến tín dụng số và ứng dụng dữ liệu trong quản trị rủi ro.", PAGES[3])
    dataset = load(data.load_digital_dataset)
    evidence = load(data.load_digital_evidence)
    ticker = None
    if dataset is not None:
        with ui.panel("digital_filter"):
            ticker = bank_picker(dataset, "digital_bank", "bank_code", "bank_name")
        row = data.select_bank(dataset, ticker, "bank_code").iloc[0].to_dict()
        ui.digital_cards(row, CRITERION_LABELS)
        st.caption("Thang điểm 0–3 · Đánh giá định tính dựa trên bằng chứng · Điểm được cung cấp từ upstream.")
        left, right = st.columns([1.05, 1], gap="medium")
        with left, ui.panel("digital_matrix"):
            ui.section_header("Ma trận chuyển đổi số", "Điểm D1–D3 của toàn bộ ngân hàng trong nghiên cứu")
            columns = ["bank_name", "bank_code"] + [f"{code}_score_0_3" for code in DIGITAL_CODES]
            labels = {**LABELS, **{f"{code}_score_0_3": code for code in DIGITAL_CODES}}
            ui.digital_matrix_table(dataset[columns], ticker)
            with st.container(key="digital_matrix_native"):
                ui.data_table(dataset[columns], labels, {f"{code}_score_0_3": "%d" for code in DIGITAL_CODES}, key="digital_matrix")
        with right, ui.panel("digital_chart"):
            ui.section_header("Điểm D1–D3 theo ngân hàng", f"Ngân hàng đang xem: {ticker} · thang điểm 0–3", "bars", "violet")
            plot(charts.digital_comparison(dataset, ticker), "digital_comparison")
    if evidence is not None:
        if ticker is None:
            ticker = bank_picker(evidence, "evidence_bank", "bank_code", "bank_name" if "bank_name" in evidence else "bank_code")
        ui.section_header(f"Bằng chứng & nguồn tham chiếu · {ticker}", "Tài liệu tham chiếu cho điểm D1–D3; trạng thái bằng chứng xem tại Nguồn dữ liệu & phương pháp.", "file", "blue")
        selected = data.select_bank(evidence, ticker, "bank_code")
        for column, code in zip(st.columns(3, gap="medium"), DIGITAL_CODES):
            with column:
                records = selected.loc[selected.indicator_code.eq(code)]
                if records.empty:
                    st.info(f"{code}: không có bản ghi bằng chứng.")
                for record in records.to_dict("records"):
                    ui.evidence_card(record, ticker)


def sources():
    ui.page_header("Nguồn dữ liệu & phương pháp", "Minh bạch nguồn tham chiếu, trạng thái bằng chứng và phạm vi của kết quả nghiên cứu.", PAGES[4])
    finance = load(data.load_financial_sources)
    evidence = load(data.load_digital_evidence)
    metadata = load(data.load_scoring_metadata)
    ranking = load(data.load_ranking)
    if ranking is not None:
        # Keep the existing review metadata contract; the sources-page CSS
        # presents it unobtrusively instead of as a prominent warning banner.
        ranking_status(ranking)
    ui.metrics([
        ("Bản ghi tài chính", len(finance) if finance is not None else "N/A", "Dữ liệu đã tổng hợp"),
        ("Bằng chứng D1–D3", len(evidence) if evidence is not None else "N/A", "Đánh giá chuyển đổi số"),
        ("Nguồn tham chiếu số", evidence.source_url.dropna().nunique() if evidence is not None and "source_url" in evidence else "N/A", "Tài liệu nguồn phân biệt"),
        ("Năm đánh giá", metadata.get("year", "N/A") if metadata else "N/A", "Phạm vi nghiên cứu"),
    ])
    left, center, right = st.columns([1.35, 1.25, 1], gap="medium")
    if finance is not None:
        with left, ui.panel("financial_sources"):
            ui.section_header("Nguồn dữ liệu tài chính", "Bao gồm năm trước dùng cho số dư bình quân", "file")
            a, b = st.columns(2)
            with a:
                year = st.selectbox("Năm dữ liệu tài chính", [None] + sorted(finance.year.unique().tolist()), format_func=lambda v: "Tất cả" if v is None else str(v), key="source_year")
            with b:
                bank = st.selectbox("Ngân hàng trong nguồn tài chính", [None] + finance.ticker.drop_duplicates().tolist(), format_func=lambda v: "Tất cả ngân hàng" if v is None else v, key="source_bank")
            filtered = finance.loc[(finance.year.eq(year) if year is not None else pd.Series(True, index=finance.index)) & (finance.ticker.eq(bank) if bank else pd.Series(True, index=finance.index))]
            preferred = ["ticker", "year", "variable", "value_clean", "unit_clean", "source_url", "status", "source", "source_title", "evidence_text", "bank"]
            provenance = [c for c in ("ticker", "year", "source", "status", "source_url") if c in filtered]
            ui.source_table(filtered[provenance].drop_duplicates(), LABELS, height=360)
            with st.expander("Chi tiết dữ liệu tài chính"):
                ui.data_table(filtered[[c for c in preferred if c in filtered]], LABELS, {"value_clean": "%.2f", "year": "%d"}, links=("source_url",), height=400, key="financial_raw", show_review=True)
            st.caption("Đơn vị ty_dong trong nguồn tương ứng tỷ đồng. URL trống được giữ là thiếu dữ liệu.")
            ui.source_summary(filtered, "source", "Tổng hợp theo loại nguồn")
    if evidence is not None:
        with center, ui.panel("digital_sources"):
            ui.section_header("Bằng chứng chuyển đổi số", "D1–D3 · nguồn, điểm và trạng thái", "layers", "violet")
            source_types = evidence.source_type.dropna().drop_duplicates().tolist() if "source_type" in evidence else []
            source_type = st.selectbox("Loại nguồn bằng chứng", [None] + source_types, format_func=lambda value: "Tất cả nguồn" if value is None else value, key="evidence_source_type")
            shown = evidence.loc[evidence.source_type.eq(source_type)] if source_type is not None else evidence
            preferred = ["bank_code", "indicator_code", "score_0_3", "status", "source_url"]
            columns = [c for c in preferred if c in evidence]
            ui.source_table(shown[columns], {**LABELS, "score_0_3": "Điểm", "indicator_code": "Chỉ tiêu", "source_url": "Nguồn"}, height=444)
            with st.expander("Chi tiết bằng chứng và tài liệu"):
                ui.data_table(shown, LABELS, links=("source_url",), height=400, key="evidence_raw", show_review=True)
            st.caption("Bản ghi đang rà soát được giữ nguyên trạng thái từ dữ liệu nguồn.")
            if "source_type" in shown:
                ui.source_summary(shown, "source_type", "Thống kê loại nguồn bằng chứng")
    with right, ui.panel("methodology"):
        ui.section_header("Phương pháp đánh giá", "12 định lượng + 3 định tính", "shield", "teal")
        ui.methodology_steps(metadata)
        criteria = load(data.load_criterion_scores)
        ui.group_weights_card(criteria)
    with ui.panel("disclaimer"):
        ui.section_header("Lưu ý & tuyên bố", symbol="shield", tone="gold")
        ui.html('<p class="disclaimer-copy">Kết quả phục vụ nghiên cứu so sánh, không phải xếp hạng tín nhiệm chính thức. Bằng chứng có trạng thái đang rà soát chưa được xác thực độc lập.</p>')
        if metadata:
            st.caption(ui.text(metadata.get("disclaimer")))
            if metadata.get("skipped_indicators"):
                st.write("Tiêu chí được upstream bỏ qua: " + ", ".join(metadata["skipped_indicators"]))
    if st.checkbox("Mở bảng tham chiếu Excel", key="show_workbook"):
        sheet = st.selectbox("Bảng tham chiếu", ["Financial_Sources", "Metric_Definitions", "Missing_Check", "Consistency_Check", "Crawl_Status"], key="workbook_sheet")
        workbook = load(data.load_workbook_sheet, sheet=sheet)
        if workbook is not None:
            ui.data_table(workbook, LABELS, links=("source_url",), key="workbook_table", show_review=True)


with st.sidebar:
    ui.html('<div class="sidebar-brand"><div class="brand-mark">B</div><div><strong>Banking Insights</strong><span>Digital Banking Group Project</span></div></div>')
    page = st.radio("Điều hướng", PAGES, key="navigation", label_visibility="collapsed")
    ui.html('<div class="sidebar-model">' + ui.icon("bars") + '<div><strong>Mô hình 12 + 3</strong><p>12 chỉ tiêu định lượng<br>3 chỉ tiêu định tính<br>Tổng 15 tiêu chí</p></div></div>')
    ui.html(f'<div class="sidebar-context"><strong>Năm đánh giá: {YEAR}</strong><p>Dữ liệu từ các nguồn công bố chính thức và dữ liệu nghiên cứu</p></div>')
    if st.button("Làm mới dữ liệu", width="stretch", key="refresh"):
        data.refresh_data()
        st.toast("Đã đọc lại dữ liệu đã xuất.")
    art = ui.overview_art("sidebar") if page == PAGES[0] else ui.bank_art("sidebar")
    ui.html('<div class="sidebar-illustration">' + art + f'<p>Digital Banking<br>Vietnam {YEAR}</p></div>')

if page == PAGES[0]:
    with st.container(key="overview_page"):
        overview()
elif page == PAGES[1]:
    with st.container(key="comparison_page"):
        comparison()
elif page == PAGES[2]:
    with st.container(key="criterion_detail_page"):
        criterion_detail()
elif page == PAGES[3]:
    with st.container(key="digital_page"):
        digital()
else:
    with st.container(key="sources_page"):
        sources()
ui.html('<div class="footer-note">Digital Banking · Nghiên cứu nhóm 2025 · Các giá trị và trạng thái được trình bày từ output của dự án.</div>')
