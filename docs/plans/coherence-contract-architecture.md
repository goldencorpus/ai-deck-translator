# Implementation Plan — Coherence Contract Architecture (P0–P2)

**Source of truth (requirements):** `lex/docs/council-sessions/2026-06-01-deck-translation-coherence/synthesis.md` (5-seat council, unanimous).
**Goal:** Whole-document translation coherence (terminology, tone, register, JA keigo/katakana) while preserving per-id mapping and reliability. Supersedes the half-wired "glossary + bigger batches".
**Scope here:** P0 (Coherence Contract) + P1 (JSONL + prompt caching) + P2 (deterministic sweep + surgical patch). P3 (cross-deck TM) is out of scope (separate, later).

---

## Architecture: Compile → Execute → Verify

```
EXTRACT (existing) → COMPILE (P0 Contract) → EXECUTE (P1 cached JSONL batches)
   → VERIFY (P2 deterministic sweep) → PATCH (P2 surgical critic) → REASSEMBLE (existing)
```

The Contract is a small artifact computed once with whole-deck view; every batch call inherits it via a cached prefix; output is recoverable JSONL; a deterministic sweep + targeted patch enforces consistency.

---

## P0 — Coherence Contract (the "compile" pass)

**New module:** `ai_deck_translator/pptx/contract.py` (engine-agnostic; reused by PPTX + native Slides).

**`build_contract(text_dict, source_language, target_language, api_key, cost_tracker=None) -> dict`**
- One `messages.create` call. Input: ALL source blocks (id + text, reading order). Output: small JSON (~1–3K tokens), `temperature=0`, `max_tokens≈3000`.
- Returns a validated dict:
  ```json
  {
    "doc_context": "1-2 sentence summary + audience",
    "register": {"style": "teineigo|plain|...", "rules": ["own-company action→謙譲語", "client action→尊敬語", "facts→です・ます", "slogans→体言止め"]},
    "deixis": {"self": "当社", "client": "貴社"},
    "glossary": {"<source term>": "<locked target>"},
    "proper_nouns": {"<name>": "<canonical katakana or roman>"},
    "header_backbone": {"<block_id>": "<locked translation of titles/headers>"}
  }
  ```
- Parse with the verbatim-first JSON path (reuse `extract_json_blocks`). On parse failure → retry once; on repeated failure → return an **empty contract** (degrade gracefully to current behavior; never block translation).
- `format_contract(contract) -> str`: renders the contract into the prompt-injection block (supersedes the current free-form `glossary` string).

**Reuse:** the existing `translate_batch(glossary=...)` injection point becomes the Contract injection point (rename param `glossary` → `contract_text` or keep `glossary` carrying the rendered contract — decide in PRD).

**Skip condition:** decks with < ~8 blocks skip the contract (overhead not worth it) — same threshold already used for the glossary stub.

### P0a — Block enrichment + register-by-block-role (GPT seat Priority 1)
Before the contract pass, enrich each block with lightweight metadata the extractor already
knows: `{id, slide_number, reading_order, role}` where `role ∈ {title, header, body_bullet,
table_header, table_cell, chart_label, speaker_note}` (derived from the extractor's element
type + shape position). This metadata is:
- passed to `build_contract` (so the contract can set the **header backbone incl. chart axis
  labels** and reading-order-aware narrative), and
- carried into each batch prompt as a per-id role hint, and
- used by the sweep's keigo check (below) to apply **role-appropriate register**, not one
  blanket rule:
  - title / header / chart_label → concise noun phrase (体言止め), NOT forced です・ます
  - body_bullet / table_cell → formal business register
  - speaker_note → です・ます prose
The contract's `register.rules` therefore has BOTH a grammatical-role axis (own-company→謙譲語,
client→尊敬語) AND a block-role axis (above). Keep enrichment cheap/deterministic (no LLM).

### P0b — Proper-noun registry: first-mention vs subsequent (Kimi)
`proper_nouns` entries may carry `{canonical, first_mention?, subsequent?, forbidden[]}` so a
name can take a fuller first form (e.g. `マイクロソフト社`) then a short form (`マイクロソフト`).
Default to a single `canonical` when no distinction is needed; the sweep validates against
`forbidden` variants. (Advanced — ship single-canonical first, add first/subsequent if needed.)

## P1 — JSONL output + prompt caching (the "execute" pass)

**JSONL protocol (replaces the single-JSON-object response):**
- Prompt instructs: "Output one JSON object per line, `{"id":"...","t":"..."}`, no markdown fences, no commas between lines; end with `{"id":"__END__"}`."
- New parser `parse_jsonl_translations(text) -> dict`: parse line-by-line, keep every well-formed record, ignore a truncated final line. Detect completion via the `__END__` sentinel.
- Completeness: missing ids = source ids not present after parse → existing retry path re-issues ONLY those ids (works for both truncation and dropped blocks). Inspect `response.stop_reason == "max_tokens"` → log + retry tail.

**Prompt caching:**
- Restructure `translate_batch` so the **system** content is a list of blocks with the LAST block (system + rendered Contract [+ optionally full source]) marked `cache_control={"type":"ephemeral"}`. The per-batch id list goes in the **user** message (after the cache breakpoint).
- **Concurrency = "seed then fan out":** fire batch 1 ALONE (writes the cache, +25%); once it returns and the cache prefix exists, fire ALL remaining batches **in parallel** (each a cache-read, ~10%). They're fully independent (the Contract — not inter-batch order — provides coherence; rolling-canonical is intentionally excluded), so there is no reason to serialize them.
  - The ONLY limit on that fan-out is the **account rate limits** (RPM / ITPM / OTPM / cache-read TPM, per model+tier) — NOT an arbitrary cap. Implement a tier-derived semaphore + **429/`retry-after` backoff**, not a fixed small number. For N=40 a 50-slide deck is ~20 batches (trivially under any tier); only very large decks (hundreds of batches → OTPM burst) need throttling.
  - All batches must fire within the ~5-min cache TTL (easy: they launch within seconds of the seed). Each hit refreshes the TTL.
- Make caching toggleable via config (`PROMPT_CACHE=true` default) for easy A/B + fallback.

**Adaptive sizing (reconciles the council's only split):** estimate output tokens for the whole deck; if `< ~70% of ANTHROPIC_MAX_TOKENS`, attempt a single full-deck JSONL call (cached prefix), else batch. JSONL recovery makes the single-call attempt safe. Keep `blocks_per_batch` as the batch fallback.

## P2 — Deterministic sweep + surgical patch (the "verify" pass)

**New module:** `ai_deck_translator/pptx/verify.py`.
- `sweep(text_dict, translated, contract) -> list[Violation]`, all deterministic (no LLM):
  - **locked-term / glossary**: every glossary source term's occurrences use the locked target (string check).
  - **proper-noun variants**: each name uses the single canonical katakana/roman form; flag variants.
  - **residual source language**: target block still contains long runs of source-script (e.g., ASCII Latin words in a JA target) → likely untranslated.
  - **keigo drift (role-aware)**: regex on sentence-final morphology — flag だ/である endings in a です・ます deck (and vice-versa) per `register.style`, BUT scope by block role: title/header/chart_label blocks are expected to be noun-phrase (体言止め) and are exempt from the です・ます requirement; body/table/note blocks are checked. Prevents false positives on headings.
  - **completeness/orphans**: every source id has exactly one non-empty target; no orphan ids.
- `patch(violations, text_dict, contract, ...) -> dict`: ONE patch-only critic call ("output only `{id, fix}` for these flagged blocks, obey the Contract"); merge fixes. Re-sweep once; remaining violations are logged (not auto-looped to avoid cost runaway).

## Integration points
- `pptx/translator.py::translate_text`: insert `build_contract` before the batch loop; pass rendered contract to every `translate_batch`; switch batch output to JSONL parse; after assembly, run `sweep`+`patch`; keep the completeness GATE in `translate_pptx` (fail-loud unchanged).
- `core/native_slides.py::translate_presentation_native`: reuse the same contract + sweep (it already calls `translate_text`).
- Config: add `PROMPT_CACHE`, `CONTRACT_ENABLED`, `SINGLE_CALL_MAX_FRACTION` (0.7) knobs.

## Testing
- Unit: `build_contract` parse + graceful-empty fallback; `parse_jsonl_translations` (complete, truncated-tail, dropped-id); `sweep` detectors (term drift, keigo-ending regex, katakana variant, residual-EN) with fixtures; cache-prefix byte-identity assertion.
- Deterministic E2E (fake translator, no API): contract injected → JSONL parse → sweep finds a seeded violation → patch fixes it → 100% coverage; multi-paragraph + table + notes preserved (extend existing test_pptx_completeness.py).
- Real E2E (one paid run): NTT/Forum deck — verify a glossary term + proper noun are consistent across slides and keigo is uniform; report token cost (expect cache discount on batches).

## Rollout / flags
- All new behavior behind config flags defaulting ON, with a documented kill-switch back to the current path (already proven). Commit per phase. No push without confirmation.

## Risks / open questions (for PRD)
1. `glossary` param rename vs reuse — backward-compat with current uncommitted edits.
2. Cache TTL vs sequential batch latency on a 50-slide deck (78 batches × few s — stays warm? measure).
3. JSONL with embedded newlines in translations (must be escaped — JSON string handles it; verify).
4. Single-call-first vs always-batch default (start always-batch + cached prefix; add single-call-first behind a flag).
5. Slides path: keigo/katakana sweep applies equally; native Slides uses batchUpdate — confirm patch re-application path.
6. Whether to inject FULL source deck in the cached prefix (max coherence, more cache-write cost) or just the Contract (cheaper). Default: Contract only; full-source behind a flag.
7. **Register UI toggle (Gemini's open Q):** expose a product-level "politeness register" choice (Business-Polite です・ます vs Plain だ/である vs CEO-formal) that overrides the contract's auto-detected `register.style`. Likely a thin pass-through to the contract — product/UX decision; record in PRD, default to auto-detect.
8. **Rate-limit tier discovery:** read the account's actual RPM/ITPM/OTPM (from a config or a 429 probe) to size the post-seed concurrency semaphore, rather than hardcoding.
