from pathlib import Path

import pandas as pd

data_dir = Path('data')
files = [
    'vnstock_articles.csv','cafef_articles.csv','ssi_articles.csv',
    'hsc_articles.csv','vndirect_articles.csv','tuoitre_articles.csv',
    'thanhnien_articles.csv','vietnamplus_articles.csv','vnexpress_articles.csv',
    'forum_articles.csv'
]
candidates = ['date','pub_date','collected_at','created_at','publish_date','updated_at']

def find_date_col(df):
    for want in candidates:
        for col in df.columns:
            if col.strip().lower() == want:
                return col
    return None

def parse_dates(s, _col_name):
    orig = s.dropna()
    if len(orig) == 0:
        return pd.Series([], dtype='datetime64[ns]')
    # Normalize: strip timezone offset like +0700 or +07:00 to avoid mixed-tz issues
    cleaned = orig.str.replace(r'[+-]\d{2}:?\d{2}$', '', regex=True)
    res = pd.to_datetime(cleaned, errors='coerce')
    # If many still NaN, try dayfirst
    if res.isna().sum() > 0.3 * len(orig):
        res2 = pd.to_datetime(cleaned, errors='coerce', dayfirst=True)
        if res2.notna().sum() > res.notna().sum():
            res = res2
    # Last resort: extract year from string
    if res.isna().all():
        yr = orig.str.extract(r'(\d{4})', expand=False)
        if yr.notna().any():
            res = pd.to_datetime(yr + '-01-01', errors='coerce')
    return res

results = {}
for fname in files:
    path = data_dir / fname
    if not path.exists():
        results[fname] = {'error': 'FILE NOT FOUND'}
        continue

    df5 = pd.read_csv(path, nrows=5)
    date_col = find_date_col(df5)
    if not date_col:
        results[fname] = {
            'error': 'NO DATE COL',
            'all_cols': list(df5.columns),
            'n_rows': len(pd.read_csv(path))
        }
        continue

    df = pd.read_csv(path, usecols=[date_col])
    n_rows = len(df)
    parsed = parse_dates(df[date_col], date_col)
    n_null = int(parsed.isna().sum())
    pct_bad = round(100 * n_null / n_rows, 1) if n_rows else 0.0
    min_d = parsed.min()
    max_d = parsed.max()
    yr_counts = parsed.dt.year.value_counts().sort_index()
    yrs = {int(k): int(v) for k, v in yr_counts.items()}

    bad_samples = []
    if n_null > 0:
        mask = parsed.isna().values
        bad_vals = df[date_col].iloc[mask].dropna().astype(str).unique()[:10]
        bad_samples = list(bad_vals)

    results[fname] = {
        'date_col': date_col,
        'min': min_d, 'max': max_d,
        'n_rows': n_rows, 'n_null': n_null, 'pct_bad': pct_bad,
        'years': yrs, 'bad_samples': bad_samples,
        'all_cols': list(df5.columns)
    }

# ── SUMMARY TABLE ──
print(f"{'SOURCE':<26} {'COL':<16} {'ROWS':>9} {'MIN':<14} {'MAX':<14} {'BAD%':>6}")
print("=" * 89)
for fname in files:
    r = results.get(fname)
    if r is None:
        print(f"{fname:<26} FILE NOT FOUND")
        print()
        continue
    if r.get('error'):
        print(f"{fname:<26} No date col. Cols: {r['all_cols']} (rows={r['n_rows']})")
        print()
        continue
    mn = str(r['min'])[:10] if pd.notna(r['min']) else '?'
    mx = str(r['max'])[:10] if pd.notna(r['max']) else '?'
    print(f"{fname:<26} {r['date_col']:<16} {r['n_rows']:>9} {mn:<14} {mx:<14} {r['pct_bad']:>5}%")
    for b in r['bad_samples'][:3]:
        print(f"{'':>26} bad: {b!r}")
    print()

# ── YEAR TABLE ──
all_years = sorted(set().union(*[
    set(r['years'].keys()) for r in results.values()
    if not r.get('error') and r.get('years')
]))
shorts = [f.replace('_articles.csv','') for f in files]

header = f"{'YEAR':<7}" + "".join(f"{s:<9}" for s in shorts)
print("YEAR-BY-YEAR RECORD COUNTS")
print("=" * len(header))
print(header)
print("-" * len(header))
for y in all_years:
    row = f"{y:<7}"
    for fname in files:
        r = results.get(fname)
        if not r or r.get('error'):
            row += f"{'':>9}"
            continue
        row += f"{r['years'].get(y, 0):<9}"
    print(row)

print()
print("=" * 70)
print("NOTES / GAPS / QUALITY ISSUES")
print("=" * 70)
for fname in files:
    r = results.get(fname)
    if not r:
        print(f"\n{fname}: FILE NOT FOUND")
        continue
    if r.get('error'):
        print(f"\n{fname}: NO DATE COLUMN. Cols={r['all_cols']}")
        continue

    notes = []
    mn = str(r['min'])[:10] if pd.notna(r['min']) else '?'
    mx = str(r['max'])[:10] if pd.notna(r['max']) else '?'

    if r['pct_bad'] > 0:
        notes.append(f"{r['pct_bad']}% bad ({r['n_null']}/{r['n_rows']})")
        if r['bad_samples']:
            notes.append(f"samples: {r['bad_samples'][:5]}")

    yl = sorted(r['years'].keys())
    if len(yl) > 1:
        gaps = []
        for i in range(len(yl)-1):
            if yl[i+1] - yl[i] > 1:
                gaps.append(f"{yl[i]+1}-{yl[i+1]-1}")
        if gaps:
            notes.append(f"year gaps: {', '.join(gaps)}")

    if pd.notna(r['min']) and r['min'].year < 1990:
        notes.append(f"pre-1990 date: {r['min'].year}")
    if pd.notna(r['max']) and r['max'].year > 2026:
        notes.append(f"future date: {r['max'].year}")

    print(f"\n{fname}: col='{r['date_col']}', rows={r['n_rows']}, range={mn} to {mx}")
    if notes:
        for n in notes:
            print(f"  -> {n}")
