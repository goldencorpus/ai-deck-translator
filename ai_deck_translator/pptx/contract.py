"""
Coherence Contract — the "compile" pass of compile-then-execute translation.

The deck translator runs text through independent batches, so no single call ever sees
the whole document. That breaks cross-slide coherence: the same term renders differently
on different slides, politeness register (keigo) drifts, proper nouns get inconsistent
katakana. This module fixes that WITHOUT needing the whole deck in every translation call:
one cheap whole-deck *input* pass produces a tiny JSON *contract* that locks the document's
decisions (glossary, proper nouns, register, deixis, header backbone). That contract is then
injected into every batch prompt, so every batch translates against the same locked decisions.

Design rationale: lex council 2026-06-01 (unanimous) + docs/plans/coherence-contract-*.md.

Engine-agnostic: reused by the PPTX path and the native Google Slides path.

Public API:
    enrich_blocks(text_dict, slide_metadata) -> {id: {slide_number, reading_order, role}}
    build_contract(text_dict, source_language, target_language, ...) -> dict
    format_contract(contract) -> str         # renders the prompt-injection block
    is_empty_contract(contract) -> bool
    estimate_output_tokens(text_dict) -> int  # for adaptive single-call sizing (P1)
"""

import json
import os
import re

import anthropic

from .. import config
from ..utils.logging import get_logger

logger = get_logger(__name__)

# A degraded/absent contract. Translation must NEVER block on a contract failure — an empty
# contract reproduces the exact pre-contract behaviour (no extra prompt injection).
EMPTY_CONTRACT: dict = {}

# Contract output cap. The contract JSON scales with deck size (header_backbone has roughly
# one entry per title/section, plus per-name proper nouns) — a 49-slide enterprise deck needs
# well over the original 3K. Sized generously; truncation is additionally salvaged below.
_CONTRACT_MAX_TOKENS = 8000

# Block roles drive both the contract (header backbone, reading-order narrative) and the
# role-aware keigo sweep. Title-ish roles are noun-phrase (体言止め) and exempt from the
# です・ます requirement; body-ish roles are checked.
_NOUN_PHRASE_ROLES = {"title", "header", "chart_label"}

_CONTRACT_KEYS = (
    "doc_context",
    "register",
    "deixis",
    "glossary",
    "proper_nouns",
    "header_backbone",
)


# --------------------------------------------------------------------------------------
# P0a — block enrichment (cheap, deterministic; no LLM)
# --------------------------------------------------------------------------------------
def _role_from_metadata(element):
    """Map an extractor element-metadata dict to a coarse block role, or None."""
    if not element:
        return None
    # The extractor tags placeholders with an explicit role when it can (most reliable).
    role = element.get("role")
    if role:
        return role
    etype = element.get("type", "")
    if etype == "presentation_title":
        return "title"
    if etype == "smartart":
        return "chart_label"
    if etype == "table_cell":
        # Caller refines header-vs-cell from the row index in the id.
        return "table_cell"
    # Fall back to the shape's name (python-pptx shape.name often says "Title"/"Subtitle").
    shape_type = (element.get("shape_type") or "").lower()
    if "subtitle" in shape_type:
        return "header"
    if "title" in shape_type:
        return "title"
    return None


def _role_from_id(block_id):
    """Derive a block role from id structure alone (works without slide metadata)."""
    if block_id == "presentation_title":
        return "title"
    if block_id.endswith("_notes"):
        return "speaker_note"
    # PPTX table cell: ..._table_r{row}c{col} ; native Slides cell: ...__r{row}c{col}
    cell = re.search(r"(?:_table_|__)r(\d+)c\d+$", block_id)
    if cell:
        return "table_header" if cell.group(1) == "0" else "table_cell"
    return "body_bullet"


def _slide_number_from_id(block_id):
    if block_id == "presentation_title":
        return 0
    match = re.search(r"slide(\d+)", block_id)
    return int(match.group(1)) if match else 0


def enrich_blocks(text_dict, slide_metadata=None):
    """
    Annotate each block with {slide_number, reading_order, role}.

    `reading_order` is the extraction order (Python dicts preserve insertion order, and the
    extractor inserts in document reading order). `role` prefers authoritative extractor
    metadata (placeholder type), then the shape name, then id-structure heuristics — so it
    degrades gracefully on the native Slides path, which passes no slide_metadata.
    """
    meta_by_id = {}
    slide_by_id = {}
    for slide in slide_metadata or []:
        if not isinstance(slide, dict):
            continue
        # Flat presentation-title metadata entry.
        if "id" in slide and "elements" not in slide:
            meta_by_id[slide["id"]] = slide
            slide_by_id[slide["id"]] = slide.get("slide_number", 0)
            continue
        slide_no = slide.get("slide_number", 0)
        for element in slide.get("elements", []):
            eid = element.get("id")
            if eid:
                meta_by_id[eid] = element
                slide_by_id[eid] = slide_no

    enriched = {}
    for order, block_id in enumerate(text_dict):
        role = _role_from_metadata(meta_by_id.get(block_id))
        if role in (None, "table_cell"):
            # Refine table header/cell from the row index in the id; otherwise id fallback.
            id_role = _role_from_id(block_id)
            role = (
                id_role if role is None else (id_role if "table" in id_role else role)
            )
        slide_number = slide_by_id.get(block_id)
        if slide_number is None:
            slide_number = _slide_number_from_id(block_id)
        enriched[block_id] = {
            "slide_number": slide_number,
            "reading_order": order,
            "role": role,
        }
    return enriched


# --------------------------------------------------------------------------------------
# Shared low-level model call (also used by verify.patch). Patch this in tests.
# --------------------------------------------------------------------------------------
def _track_usage(cost_tracker, response, label):
    """Accumulate token usage (incl. cache hits) into the shared cost tracker."""
    if cost_tracker is None:
        return
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    prompt_tokens = getattr(usage, "input_tokens", 0) or 0
    completion_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cost_tracker["total_prompt_tokens"] = (
        cost_tracker.get("total_prompt_tokens", 0) + prompt_tokens
    )
    cost_tracker["total_completion_tokens"] = (
        cost_tracker.get("total_completion_tokens", 0) + completion_tokens
    )
    cost_tracker["cache_read_tokens"] = (
        cost_tracker.get("cache_read_tokens", 0) + cache_read
    )
    cost_tracker["cache_write_tokens"] = (
        cost_tracker.get("cache_write_tokens", 0) + cache_write
    )
    logger.info(
        f"{label}: {prompt_tokens} input ({cache_read} cache-read, "
        f"{cache_write} cache-write), {completion_tokens} output tokens"
    )


def _complete(
    system,
    user,
    *,
    api_key=None,
    cost_tracker=None,
    max_tokens=3000,
    model=None,
    temperature=None,
    label="contract",
):
    """
    One text completion against the Anthropic API. `system` may be a plain string or a
    content-block list (for prompt caching). Returns the response's text. This is the single
    seam the deterministic tests patch so the contract/patch logic runs with no API key.
    """
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("CLAUDE_API_KEY"))
    response = client.messages.create(
        model=model or config.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        temperature=(
            config.ANTHROPIC_TEMPERATURE if temperature is None else temperature
        ),
        system=system,
        messages=[{"role": "user", "content": user}],
        metadata={"user_id": "anonymous_user"},
    )
    _track_usage(cost_tracker, response, label)
    # content[0] is always a TextBlock for these (non-tool, non-thinking) calls; getattr
    # keeps that behaviour while sidestepping mypy's content-block union.
    return getattr(response.content[0], "text", "")


# --------------------------------------------------------------------------------------
# P0 — build the contract
# --------------------------------------------------------------------------------------
def _validate_contract(raw):
    """Coerce a parsed object into a well-formed contract dict; drop anything malformed."""
    if not isinstance(raw, dict):
        return dict(EMPTY_CONTRACT)
    contract = {}
    contract["doc_context"] = (
        raw["doc_context"] if isinstance(raw.get("doc_context"), str) else ""
    )
    register = raw.get("register")
    if isinstance(register, dict):
        style = register.get("style")
        rules = register.get("rules")
        contract["register"] = {
            "style": style if isinstance(style, str) else "",
            "rules": (
                [r for r in rules if isinstance(r, str)]
                if isinstance(rules, list)
                else []
            ),
        }
    else:
        contract["register"] = {"style": "", "rules": []}
    deixis = raw.get("deixis")
    contract["deixis"] = (
        {k: v for k, v in deixis.items() if isinstance(v, str)}
        if isinstance(deixis, dict)
        else {}
    )
    glossary = raw.get("glossary")
    contract["glossary"] = (
        {str(k): str(v) for k, v in glossary.items() if v}
        if isinstance(glossary, dict)
        else {}
    )
    proper = raw.get("proper_nouns")
    contract["proper_nouns"] = _normalize_proper_nouns(proper)
    backbone = raw.get("header_backbone")
    contract["header_backbone"] = (
        {str(k): str(v) for k, v in backbone.items() if v}
        if isinstance(backbone, dict)
        else {}
    )
    return contract


def _normalize_proper_nouns(proper):
    """
    Proper nouns map a source name to either a canonical string or a richer object
    {canonical, first_mention?, subsequent?, forbidden[]}. Normalize both shapes to a dict.
    """
    if not isinstance(proper, dict):
        return {}
    out = {}
    for name, value in proper.items():
        if isinstance(value, str) and value.strip():
            out[str(name)] = {"canonical": value}
        elif isinstance(value, dict):
            entry: dict = {}
            canonical = value.get("canonical")
            if isinstance(canonical, str) and canonical.strip():
                entry["canonical"] = canonical
            for opt in ("first_mention", "subsequent"):
                if isinstance(value.get(opt), str) and value[opt].strip():
                    entry[opt] = value[opt]
            forbidden = value.get("forbidden")
            if isinstance(forbidden, list):
                entry["forbidden"] = [f for f in forbidden if isinstance(f, str) and f]
            if entry.get("canonical") or entry.get("first_mention"):
                out[str(name)] = entry
    return out


def is_empty_contract(contract):
    """True if the contract carries no usable coherence decisions."""
    if not contract:
        return True
    return not any(
        contract.get(key)
        for key in ("glossary", "proper_nouns", "header_backbone", "deixis")
    ) and not (contract.get("register") or {}).get("style")


def _build_source_listing(text_dict, blocks_meta):
    """Render the whole deck as an id/role/text listing in reading order for the survey."""
    lines = []
    for block_id, text in text_dict.items():
        meta = (blocks_meta or {}).get(block_id, {})
        role = meta.get("role", "")
        slide = meta.get("slide_number", "")
        clean = re.sub(r"\s+", " ", str(text)).strip()
        lines.append(
            json.dumps(
                {"id": block_id, "slide": slide, "role": role, "text": clean},
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


_CONTRACT_SYSTEM = """You are a senior localization lead preparing a STYLE CONTRACT for translating an entire slide deck from {source} to {target}.

You see the WHOLE deck. Your job is NOT to translate it. Your job is to lock the decisions that must stay consistent across every slide, so that independent translators working on different slides all produce a coherent deck.

Output ONLY a single JSON object (no prose, no markdown fences) with EXACTLY these keys:
{{
  "doc_context": "1-2 sentence summary of the deck + its audience",
  "register": {{
    "style": "the target politeness/formality register as one token (for Japanese: teineigo (です・ます) | plain (だ・である) | sonkeigo-heavy; for other languages: formal | neutral | casual)",
    "rules": ["short imperative rules, e.g. 'own-company actions -> humble form (謙譲語)', 'client actions/benefits -> honorific (尊敬語)', 'factual statements -> です・ます', 'slogans/headings -> noun-phrase (体言止め)'"]
  }},
  "deixis": {{"self": "the ONE locked self-referent (e.g. 当社)", "client": "the ONE locked client-referent (e.g. 貴社)"}},
  "glossary": {{"<source term>": "<the ONE locked target translation>"}},
  "proper_nouns": {{"<name as written in source>": {{"canonical": "<the ONE canonical target form>", "forbidden": ["<wrong variant>", ...]}}}},
  "header_backbone": {{"<block_id of a title/header/axis label>": "<the locked target translation of that anchor>"}}
}}

Guidance:
- glossary: only RECURRING domain terms that appear on multiple slides and must match everywhere. Do not list every word.
- proper_nouns: every company/person/product name. Pick ONE canonical target form (for Japanese, the standard katakana/roman form). List likely wrong variants in "forbidden".
- header_backbone: translate the deck's titles/section headers/chart-axis labels now, as anchors. Use the exact block ids from the input.
- Keep the whole object small (aim under ~2000 tokens). Omit keys you cannot fill with an empty object/array rather than guessing.
- Use the target language's natural script for values."""


def build_contract(
    text_dict,
    source_language,
    target_language,
    api_key=None,
    cost_tracker=None,
    blocks_meta=None,
):
    """
    Survey the whole deck in ONE input-heavy / output-light call and return a locked
    Coherence Contract. Never raises for translation purposes: on parse failure it retries
    once, then degrades to EMPTY_CONTRACT so the caller falls back to plain batch translation.

    Skips (returns EMPTY_CONTRACT) when the deck is smaller than CONTRACT_MIN_BLOCKS — the
    coherence overhead is not worth it for a handful of blocks.
    """
    if not config.CONTRACT_ENABLED:
        return dict(EMPTY_CONTRACT)
    if len(text_dict) < config.CONTRACT_MIN_BLOCKS:
        logger.info(
            f"Contract skipped: {len(text_dict)} blocks < CONTRACT_MIN_BLOCKS "
            f"({config.CONTRACT_MIN_BLOCKS})"
        )
        return dict(EMPTY_CONTRACT)

    source_desc = (
        "the source language (auto-detect it)"
        if str(source_language).strip().lower() in ("auto", "autodetect", "detect", "")
        else source_language
    )
    system = _CONTRACT_SYSTEM.format(source=source_desc, target=target_language)
    listing = _build_source_listing(text_dict, blocks_meta)
    user = (
        "Here is the entire deck, one JSON record per line (id, slide, role, text), in "
        "reading order. Produce the STYLE CONTRACT JSON object described in your "
        "instructions.\n\n" + listing
    )

    last_error = None
    for attempt in range(2):  # one retry
        try:
            text = _complete(
                system,
                user,
                api_key=api_key,
                cost_tracker=cost_tracker,
                max_tokens=_CONTRACT_MAX_TOKENS,
                label="contract",
            )
        except Exception as exc:  # network/API failure — never block translation
            last_error = exc
            logger.warning(f"Contract call failed (attempt {attempt + 1}): {exc}")
            continue
        parsed = _parse_contract_json(text)
        if parsed is not None:
            contract = _validate_contract(parsed)
            logger.info(
                "Coherence contract built: "
                f"{len(contract.get('glossary', {}))} glossary terms, "
                f"{len(contract.get('proper_nouns', {}))} proper nouns, "
                f"{len(contract.get('header_backbone', {}))} backbone anchors, "
                f"register='{contract.get('register', {}).get('style', '')}'"
            )
            return contract
        logger.warning(f"Contract response was not valid JSON (attempt {attempt + 1})")

    if last_error is not None:
        logger.warning("Contract degraded to EMPTY after API errors")
    else:
        logger.warning("Contract degraded to EMPTY after unparseable responses")
    return dict(EMPTY_CONTRACT)


def _parse_contract_json(text):
    """Parse the contract JSON, salvaging a truncated object if the model hit max_tokens."""
    if not text:
        return None
    # Import lazily to avoid a circular import at module load.
    from .translator import extract_json_blocks

    block = extract_json_blocks(text)
    if block is not None:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass
    # extract_json_blocks needs a closing brace; a truncated contract has none. Salvage by
    # closing the object at the last complete top-level entry (drops the half-written tail).
    salvaged = _salvage_truncated_json(text)
    if salvaged is not None:
        try:
            return json.loads(salvaged)
        except json.JSONDecodeError:
            return None
    return None


def _salvage_truncated_json(text):
    """
    Recover a truncated JSON object by closing it at the last complete top-level entry.

    Walks the string string-aware; at a top-level comma (depth 1) every nested structure is
    closed, so everything up to the last such comma is a run of complete "key": value pairs —
    appending "}" yields valid JSON. Returns None if not even the first entry completed.
    """
    start = text.find("{")
    if start == -1:
        return None
    s = text[start:]
    depth = 0
    in_str = False
    esc = False
    last_top_comma = None
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return s[: i + 1]  # a complete object after all
        elif ch == "," and depth == 1:
            last_top_comma = i
    if last_top_comma is None:
        return None
    return s[:last_top_comma] + "}"


# --------------------------------------------------------------------------------------
# Render the contract into a prompt-injection block
# --------------------------------------------------------------------------------------
def format_contract(contract):
    """Render the contract into the text block injected into every batch prompt."""
    if is_empty_contract(contract):
        return ""
    lines = ["== COHERENCE CONTRACT (obey across the ENTIRE deck) =="]
    if contract.get("doc_context"):
        lines.append(f"Document: {contract['doc_context']}")
    register = contract.get("register") or {}
    if register.get("style"):
        lines.append(f"Register / politeness: {register['style']}")
    for rule in register.get("rules", []):
        lines.append(f"  - {rule}")
    deixis = contract.get("deixis") or {}
    if deixis:
        pieces = ", ".join(f"{k}={v}" for k, v in deixis.items())
        lines.append(f"Deixis (use these exact referents): {pieces}")
    glossary = contract.get("glossary") or {}
    if glossary:
        lines.append(
            "Locked glossary (use the EXACT target wherever the source term appears):"
        )
        for src, tgt in glossary.items():
            lines.append(f"  - {src} -> {tgt}")
    proper = contract.get("proper_nouns") or {}
    if proper:
        lines.append(
            "Proper nouns (use the EXACT canonical form; never the avoid-list):"
        )
        for name, entry in proper.items():
            canonical = entry.get("canonical") or entry.get("first_mention", "")
            extra = []
            if entry.get("first_mention"):
                extra.append(f"first: {entry['first_mention']}")
            if entry.get("subsequent"):
                extra.append(f"then: {entry['subsequent']}")
            if entry.get("forbidden"):
                extra.append("avoid: " + ", ".join(entry["forbidden"]))
            suffix = f"  ({'; '.join(extra)})" if extra else ""
            lines.append(f"  - {name} -> {canonical}{suffix}")
    backbone = contract.get("header_backbone") or {}
    if backbone:
        lines.append(
            "Header backbone (use these locked translations for these block ids):"
        )
        for block_id, translation in backbone.items():
            lines.append(f"  - {block_id}: {translation}")
    lines.append("==")
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# Adaptive single-call sizing (P1 helper)
# --------------------------------------------------------------------------------------
def estimate_output_tokens(text_dict):
    """
    Conservative estimate of the output tokens needed to translate the whole deck. Used to
    decide whether a single full-deck JSONL call fits under the model's max_tokens ceiling.
    Intentionally errs high so single-call-first only triggers when comfortably safe.
    """
    total_chars = sum(len(str(v)) for v in text_dict.values())
    # ~2 chars/token for mixed CJK output, + JSONL framing per block (~12 tokens each).
    return int(total_chars / 2) + 12 * len(text_dict)
