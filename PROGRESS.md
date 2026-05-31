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

## Phase 1 — Model IDs — DONE (active code grep-clean; suite 63 passed/25 skipped/0 failed)
Active files to fix → premium=`claude-sonnet-4-6`, standard=`claude-haiku-4-5`:
- ai_deck_translator/config.py (CLAUDE_MODEL, anthropic.model)
- ai_deck_translator/pptx/translator.py (real call + estimate_cost default)
- ai_deck_translator/pptx/enhanced/models/base.py (MODEL_CLAUDE_35_* values)
- NEW/enhanced_translator_v2.py (MODEL_CLAUDE_35_* values)
- gslides_translator/config.py (claude-3-opus → claude-sonnet-4-6)
- tests/test_config.py (fixture string)
- archive/ left as-is (dead/superseded code; claude-3 strings are pricing-table keys, not calls).

## Phase 2 — Skip bug + batch bounding — DONE
- `IncompleteTranslationError(TranslationError)` added (exceptions.py) with missing_ids + total.
- `translate_text`: bounded batches (max_items=BLOCKS_PER_BATCH) + retry pass that
  re-translates genuinely-missing blocks in small batches and merges results.
- `translate_pptx`: completeness gate — computes source vs written, raises
  IncompleteTranslationError (does NOT write a partial deck), logs "N/N (100%)" on success.
- `run.py`: both PPTX call sites now catch and `sys.exit(1)` (previously ignored result).
- Batch bounding: config `blocks_per_batch=10` (+ env TRANSLATION_BLOCKS_PER_BATCH),
  `anthropic.max_tokens` 150000 → 8000 (+ env ANTHROPIC_MAX_TOKENS); batch.py gained
  `max_items` cap. The 150000/100000 values were the documented truncation cause.
- **Bonus root-cause fix (updater.py):** speaker-notes update used a
  `while len(paragraphs) > 0` loop that never terminated — the tool would HANG forever on
  ANY deck with notes. Replaced with the `text_frame.text` setter.

## Phase 3 — Tests + real E2E — DONE
- Fixed the 1 real failing test (test_setup.py → `sys.executable`; the stale audit's
  "3 failures in test_translator/test_web" no longer reproduce).
- Added tests/test_pptx_completeness.py: deterministic end-to-end coverage test (real deck
  w/ table + notes, faked translator, no API spend) asserting 0 missing blocks + the
  fail-loud gate (raises + writes nothing on a simulated skip).
- Suite: **65 passed / 25 skipped / 0 failed**.
- REAL E2E (product CLAUDE_API_KEY from repo .env; key validated live):
  `run.py --input-file sample_en.pptx --target-lang ja` → exit 0,
  **"Completeness check: 16/16 blocks translated (100%)"**. Re-extracted output:
  16/16 blocks, 0 missing, 0 unchanged, 0 without Japanese (title, subtitle, both speaker
  notes, all 6 table cells, bullets). Spend ~1090 in / 341 out tokens (≈ a few yen).
  Minor non-blocking note: multi-line bullets came back joined with full-width spaces
  (all 3 bullets present, just flattened line breaks) — content complete, not a skip.

## Phase 4 — Format preservation (the real moat) — DONE
Measured formatting on a styled deck and found the prior updater:
- corrupted **mixed-run paragraphs** (set runs[0]=full translation but left later runs →
  leftover/duplicated source-language text), and
- **stripped all table-cell formatting** (`cell.text = ...` resets bold/size/colour).
Fix (updater.py): `_apply_text_to_text_frame` / `_set_paragraph_text` / `_copy_font` —
write into the first run (keeping its font/size/colour/bold), delete leftover runs,
map newlines→paragraphs, clone first-run format onto any surplus lines. Applied to
shapes, table cells, and notes. Verified (real API): styled table header キープ
bold/18pt/colour through EN→JA; mixed-run sentence collapses to one clean run, no
leftover English. Regression test added. Suite: **66 passed / 25 skipped / 0 failed**.
Known limit (documented): intra-paragraph mixed emphasis (one bold word mid-sentence)
collapses to the paragraph's first-run format — unsolvable via block translation.

## Security (push review, pre-existing, NOT in CLI path; for the deferred SaaS phase)
- `gslides_translator/auth/google_auth.py`: pickle.load on token (legacy Slides path).
- `web/app.py`: `/download` path traversal + dev SECRET_KEY fallback (Flask web UI).
None touched by this branch; fix before any web/SaaS launch.

## Phase 5 — Visual QA (LibreOffice) + per-paragraph fix — DONE
Installed LibreOffice; rendered the real JA deck to images (`soffice --convert-to pdf`
+ `pdftoppm`) and inspected with fresh eyes (the pptx skill's QA loop). Findings:
- Slide 1 (title) ✓ CJK renders, colors/layout intact.
- Slide 3 (table) ✓ white-on-blue header + all cells preserved — client-grade.
- Slide 2 (bullets) ✗ **3 bullets collapsed into one** — the model dropped the \n when
  the body was translated as a single block.
Fix: **per-paragraph extraction** (extractor.py emits `slide{n}_shape{m}_p{k}` for
multi-paragraph shapes; updater.py sets each paragraph independently). Each bullet is now
its own translation unit → structure cannot collapse. Re-rendered: 3 distinct bullets ✓.
Regression test added. Suite: **67 passed / 25 skipped / 0 failed**.
Note: block count rises (e.g. 16→18) because bullets are now counted per line — expected.

To re-run visual QA on any deck:
  soffice --headless --convert-to pdf --outdir <dir> deck_ja.pptx
  pdftoppm -jpeg -r 120 <dir>/deck_ja.pdf <dir>/slide

## Status: engine + format fixes COMPLETE & VISUALLY VERIFIED on revive/engine-fixes.
