"""Objective-data dashboard — statistics + self-contained HTML (no server, no deps).

Reads ``data/objective/objective_v<date>.csv`` + companion news files → computes
stats → writes ``dashboard.html`` with embedded Chart.js charts. Open in a browser.

CLI: ``python -m objective.dashboard [--date YYYY-MM-DD]``
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data"
OBJ_DIR = DATA_PATH / "objective"
_TEMPLATE = Path(__file__).resolve().parent / "dashboard_template.html"


def generate_stats(csv_path: Path, news_dir: Path | None = None) -> dict:
    """Read the unified objective CSV + companion news → stats dict (pure)."""
    rows: list[dict] = []
    if csv_path.exists():
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))

    by_source = Counter(r.get("source", "") for r in rows)
    by_event = Counter(r.get("event_type", "") for r in rows)
    by_ticker = Counter(r.get("company_code", "") for r in rows)

    monthly: Counter = Counter()
    for r in rows:
        pt = (r.get("publish_time") or "")[:7]
        if pt:
            monthly[pt] += 1

    ticker_data: dict[str, dict] = {}
    for r in rows:
        t = r.get("company_code", "")
        if not t:
            continue
        if t not in ticker_data:
            ticker_data[t] = {"count": 0, "types": set(), "latest": ""}
        ticker_data[t]["count"] += 1
        if r.get("event_type"):
            ticker_data[t]["types"].add(r["event_type"])
        pt = r.get("publish_time", "")
        if pt > ticker_data[t]["latest"]:
            ticker_data[t]["latest"] = pt[:10]

    per_ticker = sorted(
        ({"ticker": t, "count": d["count"], "latest": d["latest"],
          "types": ", ".join(sorted(d["types"]))}
         for t, d in ticker_data.items()),
        key=lambda x: -x["count"],
    )

    news_count = 0
    nd = news_dir or csv_path.parent
    for f in glob.glob(str(nd / "news_unenriched_*.csv")):
        try:
            with open(f, encoding="utf-8-sig", newline="") as fh:
                news_count += sum(1 for _ in csv.DictReader(fh))
        except Exception:  # noqa: BLE001
            pass

    dates = sorted(r.get("publish_time", "")[:10] for r in rows if r.get("publish_time"))
    return {
        "total_records": len(rows),
        "tickers_covered": len(ticker_data),
        "vn30_total": 30,
        "date_range": {"oldest": dates[0] if dates else "", "newest": dates[-1] if dates else ""},
        "by_source": dict(by_source),
        "by_event_type": dict(by_event),
        "top_tickers": by_ticker.most_common(10),
        "monthly_counts": sorted(monthly.items()),
        "news_corpus": news_count,
        "per_ticker": per_ticker,
    }


def render_html(stats: dict, generated_at: str = "") -> str:
    """Render stats → self-contained HTML (reads template file + .replace tokens)."""
    tpl = _TEMPLATE.read_text(encoding="utf-8")
    rows_html = "".join(
        f"<tr><td>{t['ticker']}</td><td>{t['count']}</td>"
        f"<td>{t['latest']}</td><td>{t['types']}</td></tr>"
        for t in stats["per_ticker"]
    )
    repl = {
        "__TOTAL__": str(stats["total_records"]),
        "__TICKERS__": str(stats["tickers_covered"]),
        "__VN30__": str(stats["vn30_total"]),
        "__SOURCES__": str(len(stats["by_source"])),
        "__NEWS__": str(stats["news_corpus"]),
        "__OLDEST__": stats["date_range"]["oldest"] or "—",
        "__NEWEST__": stats["date_range"]["newest"] or "—",
        "__ROWS__": rows_html,
        "__JSON__": json.dumps(stats, ensure_ascii=False),
        "__GEN__": generated_at or date.today().isoformat(),
    }
    for k, v in repl.items():
        tpl = tpl.replace(k, v)
    return tpl


def find_latest_dataset(obj_dir: Path = OBJ_DIR) -> Path | None:
    """Find the most recent objective_v<date>.csv."""
    files = sorted(obj_dir.glob("objective_v*.csv"), reverse=True)
    return files[0] if files else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate objective-data dashboard HTML")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD version (default: latest)")
    ap.add_argument("--out", default=None, help="output HTML path")
    args = ap.parse_args()

    csv_path = (OBJ_DIR / f"objective_v{args.date}.csv") if args.date else find_latest_dataset()
    if not csv_path or not csv_path.exists():
        print(f"! no dataset found in {OBJ_DIR}")
        return 1

    stats = generate_stats(csv_path)
    html = render_html(stats, generated_at=date.today().isoformat())
    out = Path(args.out) if args.out else OBJ_DIR / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"dashboard: {out} ({stats['total_records']} records, "
          f"{stats['tickers_covered']}/{stats['vn30_total']} tickers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
