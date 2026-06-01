"""
Verify pass — deterministic sweep + surgical patch (P2).

After reassembly, cheap no-LLM checks flag where the translation violated the Coherence
Contract (a glossary term rendered differently, a proper-noun variant, residual untranslated
source, a keigo register leak). Only the flagged blocks are sent to ONE patch-only critic
call — NOT a whole-deck re-translation. This gives a correctness guarantee at ~1% of the
cost of re-translating (lex council 2026-06-01, unanimous).

The sweep is purely deterministic and must never raise. The patch never blocks: on any
failure it returns the translation unchanged. The 100%-or-fail-loud completeness gate
downstream is unaffected.
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .. import config
from ..utils.logging import get_logger
from .contract import _complete, format_contract, is_empty_contract
from .jsonl import parse_jsonl_translations

logger = get_logger(__name__)

# Max flagged blocks per patch critic call. Many flagged blocks in ONE call truncate the
# output (JSONL recovers what arrived, but dropped fixes go unapplied) — so chunk the patch.
_PATCH_CHUNK = 25

# Quality violations the patch critic can fix. Completeness/orphan ids are handled by the
# retry pass + completeness gate, not by the critic.
_FIXABLE_KINDS = {"locked_term", "proper_noun", "residual_source", "keigo"}

_NOUN_PHRASE_ROLES = {"title", "header", "chart_label"}

# Sentence-final plain-form (だ/である) — a leak in a です・ます deck. Anchored at a sentence
# boundary so mid-sentence occurrences and です/ます endings don't false-positive.
_PLAIN_ENDING = re.compile(r"(?:だ|である|だった|であった)(?:[。．！？!?]|\s|$)")
_POLITE_ENDING = re.compile(r"(?:です|ます|ました|ません|でした)(?:[。．！？!?]|\s|$)")
# A run of >=4 ASCII Latin letters — candidate untranslated source in a CJK target.
_LATIN_RUN = re.compile(r"[A-Za-z]{4,}")
_CJK_LANGS = (
    "ja",
    "japanese",
    "日本語",
    "zh",
    "chinese",
    "中文",
    "ko",
    "korean",
    "한국어",
)


@dataclass
class Violation:
    id: str
    kind: str  # locked_term | proper_noun | residual_source | keigo | missing | orphan
    detail: str


def _is_blank(value):
    return value is None or not str(value).strip()


def _is_cjk_target(target_language):
    return str(target_language).strip().lower() in _CJK_LANGS


def _register_is_polite(style):
    s = (style or "").lower()
    if any(k in s for k in ("です", "ます", "teineigo", "polite", "丁寧")):
        return True
    if any(k in s for k in ("plain", "だ", "である", "casual", "常体")):
        return False
    return None  # unknown → skip keigo check


def _roman_allowset(contract):
    """Roman/Latin tokens that are legitimately kept untranslated (from the contract)."""
    allow = set()
    for tgt in (contract.get("glossary") or {}).values():
        allow.update(_LATIN_RUN.findall(str(tgt)))
    for entry in (contract.get("proper_nouns") or {}).values():
        forms = [
            entry.get("canonical", ""),
            entry.get("first_mention", ""),
            entry.get("subsequent", ""),
        ]
        forms += entry.get("forbidden", [])  # don't re-flag a known variant as residual
        for form in forms:
            allow.update(_LATIN_RUN.findall(str(form)))
    return {tok.lower() for tok in allow}


def sweep(
    text_dict,
    translated,
    contract,
    blocks_meta=None,
    source_language=None,
    target_language=None,
):
    """
    Run all deterministic consistency checks and return a list of Violations.

    Completeness/orphan checks always run. The contract-driven quality checks (locked term,
    proper noun, residual source, keigo) only run when a contract is present — without locked
    decisions there is nothing to enforce and residual/keigo heuristics would over-flag.
    """
    violations = []
    blocks_meta = blocks_meta or {}

    # --- completeness / orphans (always) ---
    for block_id in text_dict:
        if _is_blank(translated.get(block_id)):
            violations.append(
                Violation(block_id, "missing", "no non-blank translation")
            )
    for block_id in translated:
        if block_id not in text_dict:
            violations.append(Violation(block_id, "orphan", "target id not in source"))

    if is_empty_contract(contract):
        return violations

    glossary = contract.get("glossary") or {}
    proper = contract.get("proper_nouns") or {}
    style = (contract.get("register") or {}).get("style", "")
    polite = _register_is_polite(style)
    cjk_target = _is_cjk_target(target_language)
    allow = _roman_allowset(contract) if cjk_target else set()

    for block_id, source in text_dict.items():
        target = translated.get(block_id)
        if _is_blank(target):
            continue  # already reported as missing
        target = str(target)
        source = str(source)
        role = blocks_meta.get(block_id, {}).get("role", "body_bullet")

        # locked-term / glossary: source term present -> locked target must appear.
        for term, locked in glossary.items():
            if term and term.lower() in source.lower() and locked not in target:
                violations.append(
                    Violation(
                        block_id,
                        "locked_term",
                        f"'{term}' must map to '{locked}'",
                    )
                )

        # proper nouns: never a forbidden variant; if the name is in the source, a canonical
        # form should appear in the target.
        for name, entry in proper.items():
            for bad in entry.get("forbidden", []):
                if bad and bad in target:
                    violations.append(
                        Violation(
                            block_id,
                            "proper_noun",
                            f"'{name}' uses forbidden variant '{bad}'",
                        )
                    )
            canonical_forms = [
                entry.get("canonical", ""),
                entry.get("first_mention", ""),
                entry.get("subsequent", ""),
            ]
            canonical_forms = [f for f in canonical_forms if f]
            if (
                canonical_forms
                and name.lower() in source.lower()
                and not any(f in target for f in canonical_forms)
                and name not in target  # name kept verbatim is its own (residual) check
            ):
                violations.append(
                    Violation(
                        block_id,
                        "proper_noun",
                        f"'{name}' should render as '{canonical_forms[0]}'",
                    )
                )

        # residual source language: a Latin run in a CJK target that is also in the source
        # (i.e. literally untranslated) and not an allowed roman token.
        if cjk_target:
            for run in _LATIN_RUN.findall(target):
                if run.lower() in allow:
                    continue
                if run.lower() in source.lower():
                    violations.append(
                        Violation(
                            block_id,
                            "residual_source",
                            f"untranslated source fragment '{run}'",
                        )
                    )
                    break  # one residual flag per block is enough

        # keigo drift (role-aware): only body-ish roles are held to the deck register;
        # title/header/chart_label are noun-phrase (体言止め) and exempt.
        if polite is not None and role not in _NOUN_PHRASE_ROLES:
            if polite and _PLAIN_ENDING.search(target):
                violations.append(
                    Violation(
                        block_id, "keigo", "plain (だ/である) ending in a polite deck"
                    )
                )
            elif polite is False and _POLITE_ENDING.search(target):
                violations.append(
                    Violation(
                        block_id, "keigo", "polite (です・ます) ending in a plain deck"
                    )
                )

    return violations


def _parse_fixes(text):
    """Parse the critic's {"id","fix"} JSONL. Tolerates the {"id","t"} shape too."""
    fixes = {}
    # Reuse the tolerant JSONL parser for the {"id","t"} shape...
    fixes.update(parse_jsonl_translations(text))
    # ...then add any {"id","fix"} records (the documented critic shape).
    import json

    for raw_line in (text or "").splitlines():
        line = raw_line.strip().rstrip(",").strip()
        if not line or line.startswith("```") or line in ("[", "]"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("id") and "fix" in obj:
            fixes[str(obj["id"])] = obj["fix"]
    return fixes


def patch(
    violations,
    text_dict,
    translated,
    contract,
    source_language,
    target_language,
    api_key=None,
    cost_tracker=None,
    blocks_meta=None,
):
    """
    Send ONLY the flagged blocks to one patch-only critic call and merge its fixes.

    Returns the (possibly) corrected translation dict. Never raises and never blocks: on any
    failure it returns the input translation unchanged. Re-sweeps once and logs residuals.
    """
    fixable = [v for v in violations if v.kind in _FIXABLE_KINDS and v.id in text_dict]
    if not fixable:
        return translated

    # Group reasons per block.
    reasons: dict = {}
    for v in fixable:
        reasons.setdefault(v.id, []).append(v.detail)

    contract_block = format_contract(contract)
    system = (
        f"You are a translation consistency editor fixing {target_language} slide-deck "
        "translations that violated the deck's style contract. Re-translate ONLY the blocks "
        "given, fixing the listed issues while obeying the contract. Keep meaning and length "
        "similar.\n\n" + (contract_block or "")
    )

    # Chunk the flagged blocks so no single critic call truncates (each chunk's JSONL output
    # stays well under max_tokens). Chunks are independent -> run them in parallel.
    items = list(reasons.items())
    chunks = [items[i : i + _PATCH_CHUNK] for i in range(0, len(items), _PATCH_CHUNK)]
    logger.info(
        f"Sweep flagged {len(reasons)} block(s) across {len(fixable)} violation(s); "
        f"patching in {len(chunks)} chunk(s) of up to {_PATCH_CHUNK}"
    )

    def run_chunk(chunk):
        lines = [
            "{id}\n  source: {src}\n  current: {cur}\n  issues: {iss}".format(
                id=block_id,
                src=str(text_dict[block_id]).replace("\n", " "),
                cur=str(translated.get(block_id, "")).replace("\n", " "),
                iss="; ".join(issues),
            )
            for block_id, issues in chunk
        ]
        user = (
            "Fix these blocks. Output JSON Lines, one per block, exactly "
            '{"id": "<id>", "fix": "<corrected translation>"} — no other text.\n\n'
            + "\n\n".join(lines)
        )
        try:
            text = _complete(
                system,
                user,
                api_key=api_key,
                cost_tracker=cost_tracker,
                max_tokens=4000,
                label="patch",
            )
        except Exception as exc:  # never block on a patch failure
            logger.warning(f"Patch chunk failed; skipping those blocks: {exc}")
            return {}
        return _parse_fixes(text)

    fixes: dict = {}
    if len(chunks) <= 1:
        fixes = run_chunk(chunks[0]) if chunks else {}
    else:
        workers = max(1, min(config.MAX_CONCURRENT_BATCHES, len(chunks)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for future in as_completed(
                [executor.submit(run_chunk, chunk) for chunk in chunks]
            ):
                fixes.update(future.result())

    if not fixes:
        logger.warning(
            "Patch critic returned no usable fixes; keeping unpatched translation"
        )
        return translated

    patched = dict(translated)
    applied = 0
    for block_id, fix in fixes.items():
        if block_id in text_dict and not _is_blank(fix):
            patched[block_id] = fix
            applied += 1
    logger.info(f"Applied {applied} surgical fix(es)")

    # Re-sweep once; log (do not auto-loop — avoids cost runaway).
    residual = [
        v
        for v in sweep(
            text_dict,
            patched,
            contract,
            blocks_meta=blocks_meta,
            source_language=source_language,
            target_language=target_language,
        )
        if v.kind in _FIXABLE_KINDS
    ]
    if residual:
        logger.warning(
            f"{len(residual)} quality violation(s) remain after patch (logged, not re-looped)"
        )
        for v in residual[:5]:
            logger.warning(f"  residual {v.kind} @ {v.id}: {v.detail}")
    return patched
