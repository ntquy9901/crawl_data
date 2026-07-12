"""
Morning digest — tạo bản tin sáng (markdown) từ các bài mới nhất trong news_articles.csv.
Lọc bài trong N ngày gần nhất (default 2), nhóm theo nguồn. Chạy sau daily crawl (5h sáng).

Dùng: python morning_digest.py [--days 2] [--out data/digest.md]
"""
import argparse
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data"
SOURCE_LABEL = {
    "ssi": "SSI — Bản Tin Thị Trường",
    "cafef": "Cafef — Tin thị trường",
    "vndirect": "VNDIRECT — Research notes",
    "hsc": "HSC — Research Insights",
}


def parse_date(s):
    s = str(s or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:19] if "T" in s else s, fmt).date()
        except ValueError:
            continue
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--csv", default=str(DATA / "news_articles.csv"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    df = pd.read_csv(args.csv, encoding="utf-8-sig")
    df["_d"] = df["pub_date"].apply(parse_date)
    today = date.today()
    cutoff = today - timedelta(days=args.days)
    recent = df[df["_d"].notna() & (df["_d"] >= cutoff)].sort_values("_d", ascending=False)
    nodate = df[df["_d"].isna()]

    out = Path(args.out) if args.out else DATA / f"digest_{today.isoformat()}.md"
    lines = [f"# 📈 Digest thị trường — {today.isoformat()}", "",
             f"Bài trong {args.days} ngày gần nhất (từ {cutoff.isoformat()}), theo nguồn.", ""]

    def render(src, sub, emoji=""):
        rows = sub[sub["source"] == src]
        if rows.empty:
            return
        label = SOURCE_LABEL.get(src, src)
        lines.append(f"## {emoji}{label} — {len(rows)} bài")
        for _, r in rows.iterrows():
            pd_raw = r["pub_date"]
            pd_ = (str(pd_raw)[:16].replace("T", " ")
                   if pd.notna(pd_raw) and str(pd_raw) != "nan" else "")
            lead = str(r.get("lead", "") or "")[:140]
            title = str(r.get("title", "") or "(không tiêu đề)")
            lines.append(f"- **{title}**{_fmt(pd_)}")
            if lead:
                lines.append(f"  _{lead}…_")
            lines.append(f"  {r['url']}")
        lines.append("")

    lines.append(f"### Tổng: {len(recent)} bài (có date) + {len(nodate)} bài (HSC không date)")
    lines.append("")
    render("ssi", recent, "🏦 ")
    render("cafef", recent, "📰 ")
    render("vndirect", recent, "📊 ")
    render("hsc", nodate, "🔬 ")  # HSC không date → group riêng

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"-> {out}: {len(recent)} bài gần đây + {len(nodate)} HSC")


def _fmt(s):
    return f" ({s})" if s else ""


if __name__ == "__main__":
    main()
