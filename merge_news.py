"""
Gộp các nguồn tin tức (cafef/ssi/hsc/vndirect) thành 1 file news_articles.csv
theo schema thống nhất (cột `source` ghi nguồn). Dedup theo url.
"""
import sys
from pathlib import Path

import pandas as pd

from data_classification import classify

DATA = Path(__file__).parent / "data"
# file + rename map (đưa về schema chung). Cafef dùng tên cột khác (article_url/section).
SOURCES = {
    "cafef":       ("cafef_articles.csv", {"article_url": "url", "section": "category"}),
    "ssi":         ("ssi_articles.csv",                {}),
    "hsc":         ("hsc_articles.csv",                {}),
    "vndirect":    ("vndirect_articles.csv",           {}),
    "tuoitre":     ("tuoitre_articles.csv",            {}),
    "thanhnien":   ("thanhnien_articles.csv",          {}),
    "vietnamplus": ("vietnamplus_articles.csv",        {}),
    "vnexpress":   ("vnexpress_articles.csv",          {}),
    "vneconomy":   ("vneconomy_articles.csv",          {}),
    "baodautu":    ("baodautu_articles.csv",           {}),
    "tinnhanhchungkhoan": ("tinnhanhchungkhoan_articles.csv", {}),
    "cafebiz": ("cafebiz_articles.csv", {}),
    "thoibaotaichinhvietnam": ("thoibaotaichinhvietnam_articles.csv", {}),
    "vietnamfinance": ("vietnamfinance_articles.csv", {}),
    "vietnambiz":    ("vietnambiz_articles.csv",           {}),
    "forum":       ("forum_articles.csv",              {}),
    "telegram_kakatachannel": ("telegram_kakatachannel_articles.csv", {}),
    "telegram_chungkhoanvietnammoon": ("telegram_chungkhoanvietnammoon_articles.csv", {}),
    "telegram_chungkhoanvietnam2026": ("telegram_chungkhoanvietnam2026_articles.csv", {}),
    "telegram_chungkhoanF0": ("telegram_chungkhoanF0_articles.csv", {}),
    "telegram_vnwallstreet": ("telegram_vnwallstreet_articles.csv", {}),
    "telegram_FinancialStreetVN": ("telegram_FinancialStreetVN_articles.csv", {}),
    "telegram_chungkhoantangtruong": ("telegram_chungkhoantangtruong_articles.csv", {}),
    "telegram_longshortlientuc": ("telegram_longshortlientuc_articles.csv", {}),
}
UNIFIED = [
    "source", "data_type", "title", "category", "pub_date",
    "url", "author", "lead", "body", "pdf_url", "collected_at",
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
        df["data_type"] = df["source"].map(classify)
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
