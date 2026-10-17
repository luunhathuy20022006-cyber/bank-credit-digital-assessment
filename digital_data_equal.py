
import argparse
import base64
import zlib
import csv
from collections import defaultdict
from pathlib import Path

BANKS = [('VCB','Vietcombank'), ('BID','BIDV'), ('CTG','VietinBank'),
         ('TCB','Techcombank'), ('MBB','MB')]
INDICATORS = ('D1','D2','D3')
WEIGHTS = {key: 1 / len(INDICATORS) for key in INDICATORS}  # chính xác 1/3 mỗi tiêu chí
ALLOWED_STATUSES = {'verified', 'review', 'missing'}

_EMBEDDED_EVIDENCE_ZLIB_B64 = (
    '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'
    'YhckJZd916MujsLcq6/8B5lLEZo='
)


def _prepare_input_file(path: Path, allow_embedded: bool) -> Path:
    if path.is_file():
        return path
    if not allow_embedded:
        raise FileNotFoundError(
            f'Không tìm thấy file đầu vào: {path}\n'
            'Hãy kiểm tra đường dẫn --input hoặc bỏ --input để dùng dữ liệu mẫu đi kèm script.'
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    evidence_bytes = zlib.decompress(base64.b64decode(_EMBEDDED_EVIDENCE_ZLIB_B64))
    path.write_bytes(evidence_bytes)
    print(f'CHƯA CÓ CSV -> đã tự tạo dữ liệu minh chứng mẫu tại: {path}')
    print('LƯU Ý: Điểm trong dữ liệu mẫu đang ở trạng thái review, chưa xác minh độc lập.')
    return path


def _read_rows(path):
    with path.open('r', newline='', encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def _parse_score(v, status, key):
    v = str(v or '').strip()
    if v.upper() in {'', 'NA', 'N/A', 'NULL'}:
        if status == 'verified':
            raise ValueError(f'{key}: status=verified nhưng không có điểm')
        return None
    try:
        n = int(v)
    except (ValueError, TypeError):
        raise ValueError(f'{key}: điểm phải là số nguyên 0,1,2,3 hoặc NA') from None
    if str(n) != v or not 0 <= n <= 3:
        raise ValueError(f'{key}: điểm phải là số nguyên 0..3, nhận {v!r}')
    if status == 'missing':
        raise ValueError(f'{key}: status=missing phải để điểm là NA')
    return n


def build_dataset(records):
    expected = {b for b, _ in BANKS}
    by_key = {}
    for row in records:
        code = row['bank_code'].strip().upper()
        ind = row['indicator_code'].strip().upper()
        key = (code, ind)
        if code not in expected or ind not in INDICATORS:
            raise ValueError(f'Mã không hợp lệ {key}')
        if key in by_key:
            raise ValueError(f'Trùng bản ghi {key}')
        if row['year'].strip() != '2025':
            raise ValueError(f'{key}: yêu cầu dữ liệu năm 2025')
        status = row['status'].strip().lower()
        if status not in ALLOWED_STATUSES:
            raise ValueError(f'{key}: status phải thuộc {sorted(ALLOWED_STATUSES)}')
        score = _parse_score(row['score_0_3'], status, key)
        if status == 'verified' and not row.get('source_url','').strip():
            raise ValueError(f'{key}: điểm verified phải có source_url')
        by_key[key] = {'score': score, 'status': status}

    expected_pairs = {(bank, ind) for bank in expected for ind in INDICATORS}
    if set(by_key) != expected_pairs:
        raise ValueError(f'Thiếu bản ghi: {sorted(expected_pairs-set(by_key))}; lạ: {sorted(set(by_key)-expected_pairs)}')

    output=[]
    for bank, name in BANKS:
        record={'bank_code':bank, 'bank_name':name, 'year':2025}
        all_scores=[]; statuses=[]
        for ind in INDICATORS:
            data=by_key[(bank,ind)]
            score=data['score']; statuses.append(data['status'])
            record[f'{ind}_score_0_3'] = score if score is not None else 'NA'
            record[f'{ind}_score_100'] = round(score / 3 * 100,2) if score is not None else 'NA'
            record[f'{ind}_status'] = data['status']
            if score is not None: all_scores.append(score)
        complete = len(all_scores)==len(INDICATORS)
        record['complete_3_indicators']=complete
        # Trọng số ĐỒNG ĐỀU: D1 = D2 = D3 = 1/3;
        # điểm tổng 100 = sum((điểm 0-3)/3 x trọng số) x 100.
        record['total_score_0_9'] = sum(all_scores) if complete else 'NA'
        record['weighting_rule'] = 'equal_1_3_each'
        record['digital_maturity_100'] = (
            round(sum((score / 3) * WEIGHTS[ind] for ind, score in zip(INDICATORS, all_scores)) * 100, 2)
            if complete else 'NA'
        )
        record['index_status']='review' if complete and any(s!='verified' for s in statuses) else ('verified' if complete else 'incomplete')
        record['included_in_BCDS_15']=False
        output.append(record)
    return output


def run(input_path, output_path):
    rows=build_dataset(_read_rows(input_path))
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with output_path.open('w',newline='',encoding='utf-8-sig') as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
    print(f'OK: {len(rows)} ngân hàng, D1/D2/D3 đều 1/3 -> {output_path}')
    for r in rows:
        print(f"  {r['bank_code']:3} D1={r['D1_score_0_3']} D2={r['D2_score_0_3']} D3={r['D3_score_0_3']} | chỉ số phụ={r['digital_maturity_100']} | {r['index_status']}")
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    here=Path(__file__).resolve().parent
    parser.add_argument('--input',type=Path,default=None, help='CSV đầu vào (mặc định: cạnh file .py)')
    parser.add_argument('--output',type=Path,default=here/'digital_dataset_equal_2025.csv')
    args=parser.parse_args()
    input_path = args.input if args.input is not None else here/'digital_evidence_2025.csv'
    input_path = _prepare_input_file(input_path, allow_embedded=args.input is None)
    run(input_path,args.output)
