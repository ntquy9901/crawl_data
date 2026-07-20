"""Sửa các bản ghi có ``date`` malformed trong data/vnstock_articles.csv.

Một vài card có ngày bị crawler parse sai thành dạng 3 số (thường là dải ngày trên card
hoặc format DD/MM/YY 2-số-năm). Hai nhóm:

  - DD/MM/YY (2 chữ số năm) → khôi phục năm đủ: ``20/10/11`` → ``20/10/2011``
    (xác nhận bằng pdf_filename: ``201011``, ``080808``).
  - Dải ngày không hợp lệ (VD ``25/26/27``, ``24/25/26`` — month=26/25 không thể) →
    không khôi phục được → đặt ``date=""`` (tôn trọng nguyên tắc stray-date: KHÔNG gán
    ngày sai). Các row này được log ra để check thủ công.

Idempotent: re-run an toàn (chỉ sửa row chưa đúng format). Backup ``.bak`` ghi đè lần
đầu. Không đổi cột ``id`` (dedup key — đổi sẽ làm re-crawl bị dup).
"""
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_FILE = PROJECT_ROOT / "data" / "vnstock_articles.csv"


def fix_date(raw: str) -> str:
    """Chuẩn hoá một giá trị ``date`` (format DD/MM/YYYY).

    Trả về ngày hợp lệ DD/MM/YYYY, hoặc ``""`` nếu không khôi phục được.

    - Đã đủ 4 chữ số năm + hợp lệ → giữ nguyên.
    - Năm 2 chữ số (DD/MM/YY): mở rộng năm (yy<70 → 20yy, ngược lại 19yy) trong [1990,2030].
    - MM/DD/YYYY (American) khi không mơ hồ (month>12): hoán đổi → DD/MM/YYYY
      (VD ``11/15/2024`` → ``15/11/2024``).
    - Dải ngày cả hai vế >12 (``25/26/27``) → ``""`` (không khôi phục được).
    """
    s = (raw or "").strip()
    if not s:
        return ""
    parts = s.split("/")
    if len(parts) != 3:
        return ""  # format lạ, không xử lý
    a, b, y = parts
    if not (a.isdigit() and b.isdigit() and y.isdigit()):
        return ""
    ai, bi = int(a), int(b)
    # mở rộng năm (2 chữ số → yy<70: 20yy, ngược lại 19yy)
    if len(y) == 4:
        year = int(y)
    elif len(y) == 2:
        year = 2000 + int(y) if int(y) < 70 else 1900 + int(y)
    else:
        return ""
    if not (1990 <= year <= 2030):
        return ""
    # hiểu a/b = day/month; nếu month không hợp lệ, thử hoán đổi MM/DD→DD/MM khi không
    # mơ hồ (một vế >12 → chắc chắn là ngày). VD "11/15/2024" → "15/11/2024".
    day, month = ai, bi
    if not (1 <= month <= 12):
        if 1 <= ai <= 12 and 1 <= bi <= 31:
            month, day = ai, bi
        else:
            return ""  # cả hai >12 (dải ngày "25/26/27") → unrecoverable
    if not (1 <= day <= 31):
        return ""
    return f"{day:02d}/{month:02d}/{year}"


def _is_clean(raw: str) -> bool:
    """True nếu date đã đúng format DD/MM/YYYY (4 chữ số năm, hợp lệ)."""
    s = (raw or "").strip()
    parts = s.split("/")
    if len(parts) != 3:
        return False
    d, m, y = parts
    return (y.isdigit() and len(y) == 4 and d.isdigit() and m.isdigit()
            and 1 <= int(m) <= 12 and 1 <= int(d) <= 31)


def main(csv_file: Path = CSV_FILE, dry_run: bool = False) -> dict:
    if not csv_file.exists():
        raise SystemExit(f"! không tìm thấy {csv_file}")

    with open(csv_file, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {"total": 0, "fixed": 0, "blanked": 0, "unresolved": []}
    fieldnames = list(rows[0].keys())

    fixed = 0
    blanked = 0
    unresolved: list[dict] = []
    for r in rows:
        old = (r.get("date") or "").strip()
        if _is_clean(old):
            continue
        new = fix_date(old)
        if new and new != old:
            r["date"] = new
            fixed += 1
        elif not new:
            r["date"] = ""
            blanked += 1
            unresolved.append({"id": r.get("id"), "old_date": old,
                               "title": r.get("title"), "pdf_url": r.get("pdf_url")})

    print(f"total rows={len(rows)}  fixed={fixed}  blanked(unrecoverable)={blanked}")
    for u in unresolved:
        print(f"  ! UNRESOLVED id={u['id']!r} old={u['old_date']!r}  {u['title'][:60]}")
        print(f"      pdf_url={u['pdf_url']}")

    if dry_run:
        print("(dry-run: không ghi)")
    elif fixed or blanked:
        if not (csv_file.with_suffix(".csv.bak")).exists():
            shutil.copy2(csv_file, csv_file.with_suffix(".csv.bak"))
        with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"-> đã ghi {csv_file} (backup .csv.bak)")
    else:
        print("(không có gì cần sửa)")
    return {"total": len(rows), "fixed": fixed, "blanked": blanked, "unresolved": unresolved}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sửa date malformed trong vnstock_articles.csv")
    ap.add_argument("--csv", default=str(CSV_FILE))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    main(Path(args.csv), dry_run=args.dry_run)
