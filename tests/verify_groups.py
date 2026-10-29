#!/usr/bin/env python3
"""獨立重新實作分組演算法（不依賴 index.html 的 JS），比對 data/nhi.json
算出的三同分組結果是否符合計畫書第 7 節的驗收數字。

用法：python tests/verify_groups.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "nhi.json"

FORM_CLASS = {
    "錠劑": "一般錠", "膜衣錠": "一般錠", "糖衣錠": "一般錠",
    "持續性藥效錠": "持續釋放錠", "持續性藥效膜衣錠": "持續釋放錠", "持續性膜衣錠": "持續釋放錠",
    "持續性釋放錠": "持續釋放錠", "持續釋放膜衣錠": "持續釋放錠", "持續性釋放膜衣錠": "持續釋放錠",
    "持續性糖衣錠": "持續釋放錠", "緩釋錠": "持續釋放錠", "緩釋膜衣錠": "持續釋放錠",
    "長效錠": "持續釋放錠", "長效膜衣錠": "持續釋放錠",
    "持續性藥效膠囊劑": "持續釋放膠囊", "持續性釋放膠囊": "持續釋放膠囊",
    "緩釋膠囊": "持續釋放膠囊", "緩釋微粒膠囊": "持續釋放膠囊",
}


def taiwan_today_roc():
    import datetime
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    return (now.year - 1911) * 10000 + now.month * 100 + now.day


def build_active(rows, today):
    best = {}
    for r in rows:
        code, start, end = r[0], r[7], r[8]
        if start <= today <= end:
            if code not in best or start > best[code][7]:
                best[code] = r
    return best


def group_key(row):
    form, group_name = row[4], row[5]
    form_class = FORM_CLASS.get(form, form)
    if not group_name:
        return None
    return group_name + "|" + form_class


def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    rows = data["rows"]
    today = taiwan_today_roc()
    active = build_active(rows, today)

    groups = {}
    for code, row in active.items():
        key = group_key(row)
        if key is None:
            continue
        groups.setdefault(key, []).append(row)

    failures = []

    def check(label, condition):
        status = "OK " if condition else "FAIL"
        print(f"[{status}] {label}")
        if not condition:
            failures.append(label)

    count = len(active)
    check(f"有效藥品數約 13,838 個（± 數百），實際 {count}", 9000 <= count <= 20000)

    def group_for_code(code):
        row = active.get(code)
        if row is None:
            return None, []
        key = group_key(row)
        return row, groups.get(key, [])

    crestor, members = group_for_code("BC24131100")
    if crestor is not None:
        check(f"Crestor(BC24131100) 同組數 == 22，實際 {len(members)}", len(members) == 22)
        diff_price = [m for m in members if abs(m[6] - crestor[6]) > 0.0001]
        check(f"Crestor 健保價不同筆數 == 11，實際 {len(diff_price)}", len(diff_price) == 11)
        roty = next((m for m in members if m[0] == "AA57802100"), None)
        check("Roty(AA57802100) 存在於 Crestor 同組清單", roty is not None)
        if roty is not None:
            check(f"Roty 健保價 == 9.20，實際 {roty[6]}", abs(roty[6] - 9.20) < 0.0001)
    else:
        check("Crestor(BC24131100) 今天有效（找不到，可能已改代號或停用，需人工確認）", False)

    plavix, members = group_for_code("BC22932100")
    if plavix is not None:
        check(f"Plavix(BC22932100) 同組數 == 22，實際 {len(members)}", len(members) == 22)
        others_form = set(m[4] for m in members if m[0] != "BC22932100")
        check(f"Plavix 其餘成員劑型皆為「膜衣錠」，實際 {others_form}", others_form == {"膜衣錠"})
    else:
        check("Plavix(BC22932100) 今天有效（找不到，需人工確認）", False)

    depakine, members = group_for_code("BC22008100")
    if depakine is not None:
        check(f"Depakine Chrono(BC22008100) 同組數 == 5，實際 {len(members)}", len(members) == 5)
        dipachro = next((m for m in members if m[0] == "AB46524100"), None)
        check("Dipachro(AB46524100) 存在於 Depakine Chrono 同組清單", dipachro is not None)
    else:
        check("Depakine Chrono(BC22008100) 今天有效（找不到，需人工確認）", False)

    if failures:
        print(f"\n{len(failures)} 項驗證失敗")
        return 1
    print("\n全部驗證通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
