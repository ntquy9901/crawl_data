# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

> **How to use:** Place this file as `CLAUDE.md` in your repo root. Fill the **Per-project setup** block at the bottom (the only place stack specifics go). Claude Code (and other AI coding tools that read CLAUDE.md) will follow these rules automatically. Version 1.0 — 2026-07-09.

## 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**
Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

## 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**
When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution
**Define success criteria. Loop until verified.**
Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan with per-step verify checks.

---

# Project Quality Rules

> These rules are **project-agnostic** — they apply to any language/stack. Fill the **Per-project setup** block at the bottom once per repo; do not hardcode stack details into the rules.

## Definition of Done
A task is done only when ALL are true:
- Code directly satisfies the requested change; no unrelated refactor.
- **Tests:** when behavior changes, write/run unit tests and ensure **>= 80% of the CHANGED lines are covered**, measured by **diff-coverage** (NOT total): produce a coverage report for the change, then run a diff-coverage gate (e.g. `diff-cover <coverage-report> --fail-under=80`). Ensure the change is committed or staged so the diff is measurable.
- **Checks run:** run the project's test + lint commands — or mark `Not run` with a reason. Never claim a command passed unless it actually ran.
- **Lint scope:** exclude vendored / generated / third-party tooling directories from lint (they are not the project's own code).
- **Code review (always):** run a code review (e.g. `/code-review` in Claude Code, or a PR-based adversarial peer review) and address findings before marking done. **Required for every change — including non-production (docs/config/scripts) — no exception.** Summarize the result + actions in the report.
- **Summary report:** generate a context-appropriate `docs/reports/<YYYY-MM-DD_HHMM>_summaryOfUpdate_report.md` (not a rigid template).
- **Smoke (gate):** at least one smoke test (tagged `smoke` — register the tag/marker in your test runner config) that boots the app/service and runs one happy-path (e.g. a health endpoint returns 200). The smoke command **must pass before done**. If a smoke test needs live infra / external services, mark `Not run` locally with a reason and run it in CI.
- **Impact analysis:** before a non-trivial change, identify its blast radius — find all callers/dependents/consumers (grep the symbol; check the project's registration & integration points; note cross-repo consumers). Summarize what's affected + what was verified. Flag risk if blast radius is high and not fully test-covered.
- **Similar check:** after a fix/pattern change, grep the same idiom/duplicate across the repo and any sibling / shared-scaffolding repos. Apply the same change where applicable, or list remaining instances as a follow-up. Don't fix one of N copies silently.

## Summary report (generated per change)
When a change is done, **generate** a concise, context-appropriate markdown summary — do not fill a rigid template. Save it as `docs/reports/<YYYY-MM-DD_HHMM>_summaryOfUpdate_report.md`.
- Write it to fit THIS change: include what's relevant and omit what's not — **except code review, which is always required and always summarized.**
- Cover, as applicable: what changed, files changed (path → purpose), tests + coverage %, code-review result + actions, commands actually run, risks/follow-ups, a Definition-of-Done checklist.
- Be honest: state only what truly happened; write `Not run` (with reason) for anything skipped.

## Code hygiene (all languages)
- No hidden global state / unbounded in-process caches (use bounded TTL/size caches; externalize shared state to a managed store).
- No secrets in code (use a secrets manager / env).
- No hardcoded absolute local paths.
- No production logic that lives only in a notebook.

---

## Per-project setup (fill in once per repo — this is the ONLY place stack specifics go)
- Language / toolchain: _(e.g. Python + uv, Node + npm, .NET)_
- Test command: _(e.g. `uv run pytest`, `npm test`, `dotnet test`)_
- Coverage source + diff-coverage command: _(e.g. source `src`; `pytest --cov=src --cov-report=xml` then `diff-cover coverage.xml --fail-under=80`)_
- Lint command: _(e.g. `uvx ruff check .`, `npm run lint`, `dotnet format --verify-no-changes`)_
- Lint excludes (vendored/generated dirs): _(e.g. `.agents .claude _bmad`, `node_modules`, `vendor`, `dist`)_
- Smoke command: _(e.g. `pytest -m smoke`)_
- Code-review tool: _(`/code-review`)_
- Language-specific extras: _(e.g. Python: avoid bare `except` and mutable default args; use type hints + `pathlib`)_
