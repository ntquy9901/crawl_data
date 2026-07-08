"""
Gộp các nguồn tin tức (cafef/ssi/hsc/vndirect) thành 1 file news_articles.csv
theo schema thống nhất (cột `source` ghi nguồn). Dedup theo url.
"""
import sys
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data"
# file + rename map (đưa về schema chung). Cafef dùng tên cột khác (article_url/section).
SOURCES = {
    "cafef":    ("cafef_articles.csv",    {"article_url": "url", "section": "category"}),
    "ssi":      ("ssi_articles.csv",      {}),
    "hsc":      ("hsc_articles.csv",      {}),
    "vndirect": ("vndirect_articles.csv", {}),
}
UNIFIED = [
    "source", "title", "category", "pub_date",
    "url", "author", "lead", "pdf_url", "collected_at",
]


def main():
    frames = []
    for src, (fn, renames) in SOURCES.items():
        p = DATA / fn
        if not p.exists():
            print(f"  skip {src}: {fn} không có")
            continue
        df = pd.read_csv(p, encoding="utf-8-sig")
        df = df.rename(columns=renames)
        df["source"] = src
        for c in UNIFIED:
            if c not in df.columns:
                df[c] = ""
        frames.append(df[UNIFIED])
        print(f"  {src}: {len(df)} rows")

    if not frames:
        print("! không có nguồn nào")
        sys.exit(1)
    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.drop_duplicates(subset=["url"], keep="first").reset_index(drop=True)
    out = DATA / "news_articles.csv"
    all_df.to_csv(out, index=False, encoding="utf-8-sig")
    from collections import Counter
    print(f"\n-> {out}: {len(all_df)} rows unique (theo url)")
    print("  by source:", dict(Counter(all_df["source"])))


if __name__ == "__main__":
    main()
