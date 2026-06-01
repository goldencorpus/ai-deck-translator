"""
JSONL (NDJSON) translation protocol — the recoverable wire format for the "execute" pass.

A single giant JSON object is all-or-nothing: one truncated response (hit max_tokens) and the
whole batch fails to parse. JSONL converts that to incremental commit — one
`{"id": "...", "t": "..."}` record per line, terminated by a `{"id": "__END__"}` sentinel.
A truncated stream is still valid up to its last complete line, so we keep every record that
arrived and re-issue ONLY the missing ids. This is the mechanism that gives whole-deck
coherence without whole-deck fragility (lex council 2026-06-01, unanimous).

Pure parsing/formatting only — no API, trivially unit-testable.
"""

import json

END_SENTINEL = "__END__"


def format_jsonl_instructions():
    """The output-format contract injected into the batch prompt."""
    return (
        "OUTPUT FORMAT — JSON Lines (NDJSON):\n"
        '- Output exactly one JSON object per line: {"id": "<the id>", "t": "<translation>"}\n'
        "- One line per input id, using the EXACT id from the input (never alter id formats).\n"
        "- No markdown code fences. No commas between lines. No surrounding array brackets.\n"
        "- Escape any newline inside a translation as \\n so each record stays on ONE line.\n"
        '- After the last translation, emit a final line: {"id": "__END__"}\n'
        "- Output ONLY these JSON lines — no preamble, no explanation."
    )


def parse_jsonl_translations(text):
    """
    Parse a JSONL translation stream into {id: translation}.

    Tolerant by design: skips blank lines, markdown fences, array brackets, trailing commas,
    the END sentinel, and any malformed line (e.g. a truncated final record). Whatever parsed
    cleanly is kept; missing ids are recovered by the caller's retry path.
    """
    translations: dict = {}
    if not text:
        return translations
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```") or line in ("[", "]"):
            continue
        line = line.rstrip(",").strip()
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # truncated tail or non-JSON noise — drop it, retry recovers
        if not isinstance(obj, dict):
            continue
        block_id = obj.get("id")
        if block_id is None or block_id == END_SENTINEL:
            continue
        if "t" in obj:
            translations[str(block_id)] = obj["t"]
    return translations


def has_end_sentinel(text):
    """True if the stream emitted the {"id": "__END__"} completion marker."""
    if not text:
        return False
    for raw_line in text.splitlines():
        line = raw_line.strip().rstrip(",").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("id") == END_SENTINEL:
            return True
    return False
