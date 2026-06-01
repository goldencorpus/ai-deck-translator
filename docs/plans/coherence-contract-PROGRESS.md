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
- [ ] P0  contract.py (build/format/enrich) + config flags + wire into translate_text + tests
- [ ] P0a block enrichment (role/slide/reading_order) — extractor role hint + enrich_blocks fallback
- [ ] P1  jsonl.py parser + JSONL output in translate_batch + prompt caching + seed-then-fanout + adaptive sizing
- [ ] P2  verify.py sweep + patch + wire after assembly (before completeness gate stays)
- [ ] Real paid E2E (NTT/Forum) — LAST, needs confirmation
- Each phase: deterministic no-API tests, per-phase commit. NO PUSH without confirmation.

## Baseline: 74 passed, 25 skipped (green) before changes.
