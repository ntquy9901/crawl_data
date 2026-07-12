"""VN30 universe loader (AD-5 single source of truth).

Reads ``objective/vn30.toml`` → ``{ticker: canonical_company_name}``. Ticklers
are validated against ``^[A-Z0-9]{3,5}$`` (AD-4). Used by every adapter for the
universe filter and by AD-12 (company_name binding).
"""
from __future__ import annotations

import re
import tomllib
from functools import lru_cache
from pathlib import Path

_TOML = Path(__file__).resolve().parent / "vn30.toml"
_TICKER_RE = re.compile(r"^[A-Z0-9]{3,5}$")


@lru_cache(maxsize=1)
def load_vn30(path: str | Path | None = None) -> dict[str, str]:
    """Load the VN30 universe → ``{TICKER: canonical_name}``.

    Cached (single source of truth, read once per process). Raises ``ValueError``
    on a missing ``[vn30]`` table or a malformed ticker — never silently returns
    a partial/invalid universe.
    """
    p = Path(path) if path else _TOML
    with open(p, "rb") as f:
        data = tomllib.load(f)
    entries = data.get("vn30")
    if not isinstance(entries, dict) or not entries:
        raise ValueError(f"no [vn30] table (or empty) in {p}")
    out: dict[str, str] = {}
    for ticker, name in entries.items():
        t = str(ticker).strip().upper()
        if not _TICKER_RE.match(t):
            raise ValueError(
                f"invalid VN30 ticker {ticker!r}; must match {_TICKER_RE.pattern}"
            )
        out[t] = str(name).strip()
    return out


def is_vn30(ticker: str) -> bool:
    """True if ``ticker`` (case-insensitive) is a current VN30 constituent."""
    return bool(ticker) and str(ticker).strip().upper() in load_vn30()
