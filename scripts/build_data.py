#!/usr/bin/env python3
"""下載健保藥品檔，整理成 data/nhi.json。只用 Python 標準函式庫。

失敗時以非零狀態結束，且不覆蓋既有的 data/nhi.json。
"""
import csv
import datetime
import io
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SOURCE_URL = "https://info.nhi.gov.tw/api/iode0000s01/Dataset?rId=A21030000I-E41001-001"
MIN_ROWS = 5000
MAX_RETRIES = 4
TIMEOUT_SECONDS = 180

REQUIRED_COLUMNS = [
    "藥品代號",
    "藥品英文名稱",
    "藥品中文名稱",
    "成分",
    "劑型",
    "支付價",
    "有效起日",
    "有效迄日",
    "分類分組名稱",
    "規格量",
    "規格單位",
    "ATC代碼",
    "藥品代碼超連結",
]

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "nhi.json"


def taiwan_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


def roc_date_int(dt: datetime.date) -> int:
    return (dt.year - 1911) * 10000 + dt.month * 100 + dt.day


def _relaxed_ssl_context() -> ssl.SSLContext:
    """某些政府網站的憑證缺少 Subject Key Identifier，會被 OpenSSL 3.0 的
    X509_V_FLAG_X509_STRICT 擋下（CA 憑證鏈本身仍會驗證，只是放寬這一項嚴格檢查）。"""
    ctx = ssl.create_default_context()
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


def download_csv(url: str) -> bytes:
    last_error = None
    ssl_context = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sansame-build/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=ssl_context) as resp:
                declared_length = resp.headers.get("Content-Length")
                data = resp.read()
            if declared_length is not None and int(declared_length) != len(data):
                raise ValueError(
                    f"下載長度不符：宣告 {declared_length} bytes，實際 {len(data)} bytes"
                )
            if len(data) < 10_000_000:
                raise ValueError(f"下載檔案過小（{len(data)} bytes），可能不完整")
            return data
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            last_error = exc
            print(f"[下載] 第 {attempt} 次嘗試失敗：{exc}", file=sys.stderr)
            if "CERTIFICATE_VERIFY_FAILED" in str(exc) and ssl_context is None:
                ssl_context = _relaxed_ssl_context()
            elif attempt < MAX_RETRIES:
                time.sleep(5 * attempt)
    raise RuntimeError(f"下載失敗，已重試 {MAX_RETRIES} 次：{last_error}")


def parse_roc_date(raw: str) -> int | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def parse_price(raw: str) -> float | None:
    raw = raw.strip()
    if not raw or raw == "-":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def process_csv(data: bytes, today_roc: int) -> list[list]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV 沒有標頭列")
    missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
    if missing:
        raise ValueError(f"CSV 缺少必要欄位：{missing}")

    kept_rows = []
    active_today_count = 0
    for row in reader:
        code = (row["藥品代號"] or "").strip()
        if not code:
            continue
        name_en = (row["藥品英文名稱"] or "").strip()
        name_zh = (row["藥品中文名稱"] or "").strip()
        ingredient = (row["成分"] or "").strip()
        form = (row["劑型"] or "").strip()
        group_name = (row["分類分組名稱"] or "").strip()
        spec_qty = (row["規格量"] or "").strip()
        spec_unit = (row["規格單位"] or "").strip()
        atc = (row["ATC代碼"] or "").strip()
        link = (row["藥品代碼超連結"] or "").strip()
        if not link.lower().startswith("https://"):
            link = ""

        price = parse_price(row["支付價"])
        if price is None or price <= 0:
            continue

        start = parse_roc_date(row["有效起日"])
        end = parse_roc_date(row["有效迄日"])
        if start is None or end is None:
            continue

        if end < today_roc:
            continue

        if start <= today_roc <= end:
            active_today_count += 1

        kept_rows.append(
            [code, name_en, name_zh, ingredient, form, group_name, price, start, end, spec_qty, spec_unit, atc, link]
        )

    if active_today_count < MIN_ROWS:
        raise ValueError(
            f"今天有效的藥品只有 {active_today_count} 筆，低於預期下限 {MIN_ROWS}，資料可能異常"
        )

    kept_rows.sort(key=lambda r: (r[0], r[7]))
    return kept_rows


def main() -> int:
    now = taiwan_now()
    today_roc = roc_date_int(now.date())

    try:
        raw = download_csv(SOURCE_URL)
        rows = process_csv(raw, today_roc)
    except Exception as exc:  # noqa: BLE001 - 需要明確回報並保留舊資料
        print(f"[錯誤] 更新失敗，未覆蓋既有資料：{exc}", file=sys.stderr)
        return 1

    output = {
        "generated": now.strftime("%Y/%m/%d"),
        "count": len(rows),
        "rows": rows,
    }
    new_content = json.dumps(output, ensure_ascii=False, separators=(",", ":"))

    old_rows_content = None
    if OUTPUT_PATH.exists():
        try:
            old = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
            old_rows_content = json.dumps(old.get("rows"), ensure_ascii=False, separators=(",", ":"))
        except Exception:  # noqa: BLE001 - 舊檔壞掉就視為不同，直接覆蓋
            old_rows_content = None

    new_rows_content = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    if old_rows_content == new_rows_content:
        print("[資料] 沒有變動，不覆寫 nhi.json")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(new_content, encoding="utf-8")
    print(f"[資料] 已更新 nhi.json，共 {len(rows)} 列")
    return 0


if __name__ == "__main__":
    sys.exit(main())
