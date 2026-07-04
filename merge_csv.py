#!/usr/bin/env python3
"""
Merge one or more backfill CSVs into the main data.csv, deduping by pdf_url.

Used after running parallel crawls into separate CSVs (e.g. data_2020.csv from a
metadata-only backfill + data.csv from a PDF-downloading run). For any report
present in both, the row that actually has a pdf_filename is kept, so PDF info is
preserved over metadata-only rows.

Usage:
    python merge_csv.py --inputs data/data_2020.csv
    python merge_csv.py --inputs data/data_2020.csv --dry-run
"""
import argparse
import shutil
from pathlib import Path

import pandas as pd

from config import CSV_FILE


def main():
    ap = argparse.ArgumentParser(description='Merge backfill CSVs into the main data.csv')
    ap.add_argument('--main', default=str(CSV_FILE), help=f'Main CSV (default: {CSV_FILE})')
    ap.add_argument('--inputs', nargs='+', required=True, help='Extra CSV file(s) to merge in')
    ap.add_argument('--dry-run', action='store_true', help='Report only, do not write')
    args = ap.parse_args()

    main_p = Path(args.main)
    if not main_p.exists():
        raise SystemExit(f'Main CSV not found: {main_p}')

    df_main = pd.read_csv(main_p, encoding='utf-8-sig', dtype=str).fillna('')
    print(f'Main  {main_p}: {len(df_main)} rows')
    frames = [df_main]
    for f in args.inputs:
        p = Path(f)
        if not p.exists():
            print(f'  ! {p}: missing, skipped')
            continue
        d = pd.read_csv(p, encoding='utf-8-sig', dtype=str).fillna('')
        frames.append(d)
        print(f'  + {p}: {len(d)} rows')

    df = pd.concat(frames, ignore_index=True)

    # Dedup by pdf_url; prefer rows that carry a pdf_filename (PDF info wins).
    has_pdf = (df['pdf_filename'].astype(str).str.strip() != '').astype(int)
    df = df.assign(_has_pdf=has_pdf).sort_values('_has_pdf', ascending=False)
    before = len(df)
    df = df.drop_duplicates(subset='pdf_url', keep='first').drop(columns='_has_pdf').reset_index(drop=True)
    print(f'Dedup by pdf_url: {before} -> {len(df)} (removed {before - len(df)})')

    if args.dry_run:
        print('Dry run — nothing written.')
        return

    backup = main_p.with_suffix(main_p.suffix + '.bak')
    shutil.copy2(main_p, backup)
    df.to_csv(main_p, index=False, encoding='utf-8-sig')
    print(f'Merged -> {main_p}  (backup: {backup})')


if __name__ == '__main__':
    main()
