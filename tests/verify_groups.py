#!/usr/bin/env python3
"""獨立重新實作分組演算法（不依賴 index.html 的 JS），比對 data/nhi.json
算出的三同分組結果是否符合「ATC碼加入三同定義.md」第 6 節的驗收數字。

用法：python tests/verify_groups.py
"""
import json
import re
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

RANGE_RE = re.compile(r"\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?")
CONTENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(MCG|MIU|GM|MG|UG|ML|IU|U|G)\b")


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


def content_key(ingredient):
    s = ingredient.upper()
    tokens = []
    for num, unit in CONTENT_RE.findall(s):
        val = float(num)
        if unit in ("G", "GM"):
            val *= 1000
            unit = "MG"
        elif unit in ("MCG", "UG"):
            val *= 0.001
            unit = "MG"
        tokens.append(f"{round(val, 6)}{unit}")
    tokens.sort()
    return "|".join(tokens)


def group_key(row):
    ingredient, form, group_name, atc = row[3], row[4], row[5], row[11]
    if not group_name:
        return None
    form_class = FORM_CLASS.get(form, form)
    key = f"{group_name}\x01{form_class}\x01{atc or ''}"
    if RANGE_RE.search(group_name):
        key += "\x01" + content_key(ingredient)
    return key


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

    codiovan, members = group_for_code("BC23109100")
    if codiovan is not None:
        check(f"Co-Diovan(BC23109100) 同組數 == 5，實際 {len(members)}", len(members) == 5)
        check("Co-Diovan 同組不含單方 Diovan(BC23373100)",
              not any(m[0] == "BC23373100" for m in members))
    else:
        check("Co-Diovan(BC23109100) 今天有效（找不到，需人工確認）", False)

    diovan, members = group_for_code("BC23373100")
    if diovan is not None:
        check(f"Diovan(BC23373100) 同組數 == 11，實際 {len(members)}", len(members) == 11)
        check("Diovan 同組不含複方 Co-Diovan(BC23109100)",
              not any(m[0] == "BC23109100" for m in members))
    else:
        check("Diovan(BC23373100) 今天有效（找不到，需人工確認）", False)

    plavix, members = group_for_code("BC22932100")
    if plavix is not None:
        check(f"Plavix(BC22932100) 同組數 == 21，實際 {len(members)}", len(members) == 21)
    else:
        check("Plavix(BC22932100) 今天有效（找不到，需人工確認）", False)

    crestor, members = group_for_code("BC24131100")
    if crestor is not None:
        check(f"Crestor(BC24131100) 同組數 == 22，實際 {len(members)}", len(members) == 22)
        diff_price = [m for m in members if abs(m[6] - crestor[6]) > 0.0001]
        check(f"Crestor 健保價不同筆數 == 11，實際 {len(diff_price)}", len(diff_price) == 11)
    else:
        check("Crestor(BC24131100) 今天有效（找不到，需人工確認）", False)

    depakine, members = group_for_code("BC22008100")
    if depakine is not None:
        check(f"Depakine Chrono(BC22008100) 同組數 == 5，實際 {len(members)}", len(members) == 5)
        dipachro = next((m for m in members if m[0] == "AB46524100"), None)
        check("Dipachro(AB46524100) 存在於 Depakine Chrono 同組清單", dipachro is not None)
    else:
        check("Depakine Chrono(BC22008100) 今天有效（找不到，需人工確認）", False)

    lixiana, members = group_for_code("BC26600100")
    if lixiana is not None:
        check(f"Lixiana 30mg(BC26600100) 同組數 == 2，實際 {len(members)}", len(members) == 2)
        check("Lixiana 30mg 同組含 X000362100",
              any(m[0] == "X000362100" for m in members))
        check("Lixiana 30mg 同組不含 15mg 的健保碼 BC26601100",
              not any(m[0] == "BC26601100" for m in members))
    else:
        check("Lixiana 30mg(BC26600100) 今天有效（找不到，需人工確認）", False)

    alen1, alen1_members = group_for_code("AC57366100")
    alen2, alen2_members = group_for_code("BA25104100")
    if alen1 is not None and alen2 is not None:
        check("AC57366100 與 BA25104100 互不列出（Alendronate 特例）",
              not any(m[0] == "BA25104100" for m in alen1_members)
              and not any(m[0] == "AC57366100" for m in alen2_members))
    else:
        check("Alendronate 特例兩個健保碼今天都有效（找不到，需人工確認）", False)

    if failures:
        print(f"\n{len(failures)} 項驗證失敗")
        return 1
    print("\n全部驗證通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
