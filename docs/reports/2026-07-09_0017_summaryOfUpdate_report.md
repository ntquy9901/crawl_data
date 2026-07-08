# Phase -1: QA Infrastructure Setup — Summary

**Date:** 2026-07-09 00:17
**Scope:** Setup QA infrastructure required by the new CLAUDE.md "Project-Specific Quality Assurance Rules" before the body-extraction sprint.

## What changed

Brought the project onto the new QA toolchain (Python 3.13 + uv + pytest + ruff) and established a ruff-clean baseline so the DoD gate (`uvx ruff check .`, `pytest -m smoke`, `/code-review`) is enforceable for all future code.

## Files

| File | Purpose |
|---|---|
| `.python-version` (new) | Pin Python 3.13 for uv |
| `pyproject.toml` (new) | Runtime + dev deps, `[tool.ruff]` exclude, `[tool.pytest.ini_options]` smoke marker + pythonpath, `[tool.coverage]`, `[tool.uv] package=false` |
| `uv.lock` (new) | Locked dependency versions (commit for reproducibility) |
| `.gitignore` (edit) | Add `.coverage`, `coverage.xml` |
| `tests/smoke/test_smoke_boot.py` (new) | Smoke gate: core modules import under 3.13 venv, schema constants present |
| `tests/fixtures/README.md` (new) | Placeholder for phase-1 sample HTML/PDF fixtures |
| `CLAUDE.md` (edit) | Added QA rules, adapted to crawler (removed BMAD/Azure/MCP/A2A mentions) |
| 9 `.py` files (edit) | Ruff baseline cleanup: 74 `--fix` auto + manual E501/E702/E722/B905 fixes |

## Tests & coverage

- **Smoke gate:** `uv run pytest -m smoke -q` → **1 passed**.
- **Diff-coverage (≥80%):** *Not run* — reason: phase -1 introduces **no behavior change** (config + formatting + verified-equivalent lint wraps). Equivalence verified via full-module import + smoke + ruff, not via line coverage.
- **Import check:** all 9 crawler modules + `utils/*` import cleanly under Python 3.13.14.

## Commands actually run

```bash
uv sync                                     # all deps + dev on 3.13.14 (.venv)
uv run python -c "import ..."               # ALL IMPORTS OK
uvx ruff check --fix .                      # 74 auto-fixes applied
uvx ruff check .                            # All checks passed! (after manual fixes)
uv run pytest -m smoke -q                   # 1 passed
```

## `/code-review` result (medium effort)

3 focused angles (correctness of semantic changes, ruff-auto-fix-removal audit, conventions-vs-CLAUDE.md).

- **Correctness:** `[]` — all semantic changes safe:
  - `except:` → `except Exception:` (crawler.py) — only narrows to selector errors, no longer swallows KeyboardInterrupt.
  - `zip(..., strict=False)` (proxy_manager.py) — lists equal-length by construction via `asyncio.gather`; preserves truncation behavior.
  - JS `querySelector` selector extracted to `const sel` (crawler.py) — equivalent JS.
  - All E501 wraps — f-string implicit concatenation identical; `UNIFIED` list same 9 elements/order; chained `drop_duplicates().drop().reset_index()` preserved.
- **Auto-fix audit:** `[]` — removed imports all safe: `re` has a local import in-method; `should_use_proxy`/`LOG_PATH` genuinely unused; `Optional[X]`→`X | None` modernization valid on 3.13.
- **Conventions:** 1 finding — `docs/papers/FinMarBa_dataset.md` is a **pre-existing unrelated change** (BPMN/D365 notes, paste-error from an earlier session). **Action:** exclude from the phase -1 commit (no code change needed).

## Impact analysis (blast radius)

- **Daily production flow UNCHANGED:** Task Scheduler `CrawlDailyNews` + `run_daily_all.ps1` + CLAUDE.md run-commands still invoke the system `python` (3.11). `.python-version`/`requires-python>=3.13` only affect the new uv `.venv` (dev/QA). Migration of daily commands to `uv run` is deferred until 3.13 is verified in a real crawl.
- **Ruff baseline:** 103 errors → 0. Formatting-only (verified: imports + smoke unchanged). No runtime behavior change.
- **Affected consumers:** none broken. `merge_news.py`, `morning_digest.py`, `dedup.py` all use pandas/DictReader — schema-unaffected by the lint wraps.

## Risks / follow-ups

1. **Daily-flow migration:** commands + Task Scheduler still on python 3.11; move to `uv run` after a real crawl confirms 3.13 stability.
2. **`requirements.txt` drift:** now redundant vs `pyproject.toml`. Either `uv export` to regenerate it or remove it (separate decision).
3. **Body-extraction sprint (phase 0–7)** can now proceed under the enforced DoD gate.

## Definition of Done checklist

- [x] Code satisfies the requested change (QA infra + clean baseline)
- [~] Tests ≥80% diff-coverage — *Not run* (no behavior change; verified via import+smoke+ruff)
- [x] `uvx ruff check .` — All checks passed
- [x] ruff exclude configured (`.claude`, `data`, `aggregated`, `docs`, `pdf`)
- [x] `/code-review` run; 1 finding (orphan file, excluded — no code change)
- [x] Summary report created (this file)
- [x] No unrelated refactor (lint wraps authorized by "clean baseline"; orphan `docs/papers/...` flagged for exclusion)
- [x] Smoke gate: `pytest -m smoke` passes
- [x] Impact analysis above
- [~] Similar check — N/A (no pattern fix in this phase)
