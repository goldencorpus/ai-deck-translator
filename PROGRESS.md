# Revive ai-deck-translator — Engine Fixes (branch: revive/engine-fixes)

Goal: CLI reliably translates a full deck with ZERO skipped text blocks, fail loudly otherwise.
Started from branch `v2` @ 5493a27.

Repo layout note: REAL code is the nested repo
`/Users/emmanuel/Documents/Dev/ai-deck-translator/ai-deck-translator/`
(outer dir is an agent wrapper; docs live in outer `docs/` + `.claude/`).
Package dir: `ai_deck_translator/`. Real PPTX CLI entry: repo-root `run.py`
(`run.py --input-file X.pptx --source-lang en --target-lang ja`), which calls
`ai_deck_translator/pptx/translator.py::translate_pptx`.

## Phase 0 — Orient & venv — DONE
- Read project-intel, business-plan-2026 (§8 skip bug), productization-plan, PPTX_TRANSLATION_FIX.
- Recreated `.venv` (python3.14), `pip install -e .` OK, package imports OK.
- Installed `setuptools` into venv (needed by setup.py; 3.14 venvs omit it).
- Untracked `.venv/` (5132 files were committed by mistake) + added to `.gitignore`.
- Baseline: with CLAUDE_API_KEY loaded from repo `.env`, suite = 62 passed / 25 skipped /
  **1 failed** (test_setup.py — bare `"python3"` escaped the venv). The stale audit's
  "3 failures in test_translator/test_web" no longer reproduce (fixed earlier in 5493a27).

## Phase 1 — Model IDs — IN PROGRESS
Active files to fix → premium=`claude-sonnet-4-6`, standard=`claude-haiku-4-5`:
- ai_deck_translator/config.py (CLAUDE_MODEL, anthropic.model)
- ai_deck_translator/pptx/translator.py (real call + estimate_cost default)
- ai_deck_translator/pptx/enhanced/models/base.py (MODEL_CLAUDE_35_* values)
- NEW/enhanced_translator_v2.py (MODEL_CLAUDE_35_* values)
- gslides_translator/config.py (claude-3-opus → claude-sonnet-4-6)
- tests/test_config.py (fixture string)
- archive/ left as-is (dead/superseded code; claude-3 strings are pricing-table keys, not calls).

## Phase 2 — Skip bug + batch bounding — TODO
- Completeness gate (source count vs written), retry pass for still_missing, FAIL loudly,
  log "N/N blocks translated (100%)". Bound batch to ~10 blocks; sane max_tokens.

## Phase 3 — Tests + real E2E — TODO
- Fix the 1 failing test (test_setup.py → sys.executable). Add 100%-coverage test.
- Real CLI run on a sample multi-slide deck (tables + notes) EN→JA, open output, verify 0 skips.
- E2E uses repo `.env` CLAUDE_API_KEY (product's own key — small COGS, NOT Lex infra).
