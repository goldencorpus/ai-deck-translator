# PRD — Translation Coherence Contract (P0–P2)

**Status:** Draft for /evaluate-plan. **Design rationale:** `lex/docs/council-sessions/2026-06-01-deck-translation-coherence/synthesis.md`. **Implementation plan:** `coherence-contract-architecture.md`.

## 1. Problem
The deck translator translates text blocks in independent batches, so the model never sees the whole document. Result: the same term/phrase is rendered differently across slides; tone/register drifts; Japanese politeness level (keigo) and katakana transliteration of proper nouns are inconsistent. For a paid product selling to Japanese enterprises (¥1,500–10,000/deck), inconsistent client-facing decks are a dealbreaker.

## 2. Goals / success criteria
- **G1 Terminology consistency:** a recurring source term/proper noun maps to ONE target form across the entire deck (≥99% of occurrences).
- **G2 Register consistency:** one keigo/politeness register across the deck per block-role policy (no だ/である leaks into a です・ます deck; headings stay 体言止め).
- **G3 Reliability preserved:** never ship a partial deck; a truncated/failed generation degrades to retrying only the missing blocks (no whole-deck loss). The existing 100%-or-fail-loud completeness gate stays.
- **G4 Cost/latency bounded:** added cost ≤ ~2× current per-deck (target: less, via prompt caching); a 50-slide deck still completes in minutes.
- **G5 Works on both engines:** PPTX (python-pptx) and native Google Slides (batchUpdate).

## 3. Non-goals (this release)
- Cross-deck Translation Memory (P3) — separate later release.
- Rolling-canonical / inter-batch continuity (Contract replaces the need).
- Intra-run mixed-format preservation (known, separate limitation).

## 4. Functional requirements
- **FR1 Coherence Contract (P0):** one whole-deck-input pass produces a small JSON contract: `doc_context`, `register` (style + grammatical-role rules + block-role rules), `deixis` (self/client), `glossary`, `proper_nouns` (canonical [+first/subsequent, forbidden]), `header_backbone` (titles/headers/chart-axis labels). Injected into every batch prompt. Degrades to empty contract on parse failure (never blocks).
- **FR2 Block enrichment (P0a):** each block carries `{slide_number, reading_order, role}`; role drives block-role register + sweep scoping.
- **FR3 JSONL output (P1):** batches output one `{"id","t"}` record per line + `__END__` sentinel; truncation → keep parsed lines, retry only missing ids; inspect `stop_reason`.
- **FR4 Prompt caching (P1):** byte-identical cached prefix (system + contract [+ optional full source]); seed-then-fan-out concurrency; rate-limit (429) aware; config-toggleable.
- **FR5 Adaptive sizing (P1):** single full-deck JSONL attempt when est. output < 70% ceiling, else batched; both recover missing ids.
- **FR6 Deterministic sweep (P2):** no-LLM checks — locked-term/glossary, proper-noun variants, residual-source-language, role-aware keigo-ending, completeness/orphans.
- **FR7 Surgical patch (P2):** one patch-only critic call returns `{id, fix}` for flagged blocks only; merge; re-sweep once; log residual.
- **FR8 Both engines (G5):** contract + sweep reused by `pptx/translator.py` and `core/native_slides.py`.

## 5. Non-functional requirements
- **NFR1** Every new behavior behind a config flag defaulting ON, with a kill-switch to today's proven path.
- **NFR2** No secret/PII logging; confidential deck text never echoed to logs.
- **NFR3** Deterministic, no-API unit + E2E tests for all new logic; one real paid E2E for acceptance.
- **NFR4** Per-phase commits; no push without confirmation.

## 6. Acceptance criteria
- **AC1 (G1):** On a fixture deck seeding a term used on 5 slides + a proper noun on 4, output uses the single locked form everywhere; the sweep reports 0 term/proper-noun violations.
- **AC2 (G2):** On a です・ます deck with a seeded だ/である body block, the sweep flags it and the patch corrects it; titles are NOT flagged.
- **AC3 (G3):** Simulated truncation (JSONL tail dropped) → only missing ids retried, final deck 100% complete; full failure still raises IncompleteTranslationError (no partial write).
- **AC4 (G4):** Batch calls show cache-read hits after the seed (token report); per-deck cost within target.
- **AC5 (G5):** Same contract path runs for a PPTX deck and a native Slides deck.
- **AC6 (regression):** existing 72+ tests stay green; the real NTT/Forum deck still reaches 100% with improved cross-slide consistency.

## 7. Open product decisions
- **OD1 Register UI toggle:** expose Business-Polite / Plain / CEO-formal override of auto-detected register? Default: auto-detect; toggle is a thin pass-through (decide before shipping UI).
- **OD2 Full-source-in-prefix:** default Contract-only; full-source behind a flag (cost vs max coherence).
- **OD3 Single-call-first default:** start always-batch+cached; enable single-call-first behind a flag after measurement.

## 8. Rollout
P0 → P0a → P1 → P2, each flag-gated and independently shippable; deterministic tests per phase; one real E2E at the end. Implementation may run in a fresh session and/or via /workflow (per-phase agents) — plan + this PRD + synthesis are the durable inputs.
