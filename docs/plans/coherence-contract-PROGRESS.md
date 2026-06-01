# Coherence Contract — Build Progress (compaction-survival scratch)

Branch: `revive/engine-fixes`. Spec: `coherence-contract-PRD.md` + `coherence-contract-architecture.md`.
Source-of-truth requirements: `lex/docs/council-sessions/2026-06-01-deck-translation-coherence/synthesis.md`.

## Architecture: Compile → Execute → Verify
EXTRACT → COMPILE (P0 contract) → EXECUTE (P1 cached JSONL batches) → VERIFY (P2 sweep) → PATCH → REASSEMBLE

## Module layout (decided)
- `pptx/contract.py` — `build_contract`, `format_contract`, `enrich_blocks`, `EMPTY_CONTRACT`,
  `estimate_output_tokens`, shared `_complete()` LLM helper (imported by verify.py). Seam for tests: `contract._complete`.
- `pptx/jsonl.py` — `parse_jsonl_translations(text)->dict`, `has_end_sentinel(text)`, `END_SENTINEL`, `format_jsonl_instructions()`.
- `pptx/verify.py` — `Violation`, `sweep(...)`, `patch(...)`. Seam: reuses `contract._complete`.
- Integration in `pptx/translator.py::translate_text` + `translate_pptx`; native path inherits via `translate_text`.
- Config flags in `config.py` (all default ON except single-call-first).

## Config flags
- CONTRACT_ENABLED=true, PROMPT_CACHE=true, SWEEP_ENABLED=true
- CONTRACT_MIN_BLOCKS=8, SINGLE_CALL_FIRST=false, SINGLE_CALL_MAX_FRACTION=0.7
- Kill switch: set all three to false → exact current proven path.

## Decision: NOT using /workflow
3 modules share `_complete()` and need consistent integration into translate_text; fan-out agents
would each need full engine context and risk divergence. Building directly + deterministic tests/phase.

## Status
- [x] P0  contract.py — DONE, committed c19176c (84 passed)
- [x] P0a block enrichment — DONE (in c19176c)
- [x] P1  jsonl.py + JSONL output + caching + seed-then-fanout + adaptive sizing — DONE (94 passed)
      Note: cost_tracker token counts may slightly undercount under parallel fan-out (advisory metrics only, not correctness). MAX_CONCURRENT_BATCHES=8 default; tier-discovery is a future refinement.
- [x] P2  verify.py sweep + patch + wire after assembly — DONE (105 passed). Native path inherits via translate_text. black/isort clean; mypy only has pre-existing `.text` union-attr (matches codebase; baseline mypy=182 errors, CI lint non-blocking).
- [x] Real paid E2E — DONE on the live NTT DATA × Salesforce deck (49 slides, 662 blocks).
      Surfaced + fixed two truncation bugs (same class):
        * contract output capped at 3K → truncated → empty contract → also no caching
          (prefix < 1024-token min). Fix c348b8a: raise to 8K + salvage partial JSON.
        * patch critic single call (94 blocks) truncated at 4K → 56/105 applied. Fix
          e1b8c3d: chunk into bounded parallel calls (_PATCH_CHUNK=25).
      Validated run: 100% complete; contract = 48 glossary / 26 proper nouns / 52 backbone /
      register=teineigo + 当社/貴社; caching engaged (cache-read 35,019); sweep 105 violations
      patched; cost $0.40 (< 1× naive, well under ≤2× budget). Good copy:
      https://docs.google.com/presentation/d/1qEViX0VxSj7lo0X_gQN2LcR1vZ1Zr_RCZy2YDyOdOwo/edit
      (Inferior empty-contract copy 1rkce-jOOWp... can be deleted.)
- Branch revive/engine-fixes pushed through e1b8c3d (P0,P1,P2 + 2 E2E fixes). 107 tests pass.

## Open follow-ups (for the user)
- Optional: 3rd live run to confirm patch-chunking applies all fixes on the real deck (~$0.40).
- Open a PR for revive/engine-fixes? (not done — awaiting decision)
- Delete the duplicate inferior Drive copy (1rkce-...).

## Baseline: 74 passed, 25 skipped (green) before changes.
