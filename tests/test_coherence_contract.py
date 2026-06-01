"""
Deterministic tests for the Coherence Contract compile pass (P0 + P0a).

No API key required: the single model-call seam (`contract._complete`) is patched, so these
exercise the parsing, validation, graceful-degradation, rendering, and block-enrichment
logic with zero cost.
"""

import json
import unittest
from unittest.mock import patch

from ai_deck_translator.pptx import contract as contract_mod
from ai_deck_translator.pptx.contract import (
    build_contract,
    format_contract,
    enrich_blocks,
    is_empty_contract,
    estimate_output_tokens,
    EMPTY_CONTRACT,
)

SAMPLE_CONTRACT_JSON = {
    "doc_context": "A QBR deck for enterprise clients.",
    "register": {
        "style": "teineigo (です・ます)",
        "rules": ["own-company actions -> 謙譲語", "headings -> 体言止め"],
    },
    "deixis": {"self": "当社", "client": "貴社"},
    "glossary": {"Revenue": "売上", "churn": "解約率"},
    "proper_nouns": {
        "Microsoft": {"canonical": "マイクロソフト", "forbidden": ["ミクロソフト"]},
        "Acme": "アクメ",
    },
    "header_backbone": {"slide1_shape0": "四半期業績レビュー"},
}


def _deck(n):
    return {f"slide1_shape{i}": f"text number {i}" for i in range(n)}


class TestBuildContract(unittest.TestCase):
    def test_parses_and_validates_a_well_formed_contract(self):
        raw = (
            "```json\n" + json.dumps(SAMPLE_CONTRACT_JSON, ensure_ascii=False) + "\n```"
        )
        with patch.object(contract_mod, "_complete", return_value=raw):
            result = build_contract(_deck(10), "en", "ja", api_key="x")
        self.assertEqual(result["glossary"]["Revenue"], "売上")
        self.assertEqual(result["register"]["style"], "teineigo (です・ます)")
        # Short-form proper noun normalized to {canonical: ...}
        self.assertEqual(result["proper_nouns"]["Acme"], {"canonical": "アクメ"})
        self.assertEqual(
            result["proper_nouns"]["Microsoft"]["forbidden"], ["ミクロソフト"]
        )
        self.assertFalse(is_empty_contract(result))

    def test_skips_small_decks(self):
        # Below CONTRACT_MIN_BLOCKS the model is never called.
        with patch.object(contract_mod, "_complete") as m:
            result = build_contract(_deck(3), "en", "ja", api_key="x")
        m.assert_not_called()
        self.assertEqual(result, EMPTY_CONTRACT)

    def test_degrades_to_empty_on_unparseable_response(self):
        with patch.object(
            contract_mod, "_complete", return_value="sorry, no JSON here"
        ) as m:
            result = build_contract(_deck(10), "en", "ja", api_key="x")
        # Retries once, then degrades.
        self.assertEqual(m.call_count, 2)
        self.assertTrue(is_empty_contract(result))

    def test_salvages_truncated_contract(self):
        # Model hit max_tokens mid header_backbone: object is unterminated. We should recover
        # a PARTIAL contract (the complete leading entries), not degrade to empty.
        truncated = (
            '{\n"doc_context": "QBR",\n'
            '"register": {"style": "teineigo (です・ます)", "rules": []},\n'
            '"glossary": {"Revenue": "売上", "churn": "解約率"},\n'
            '"proper_nouns": {"Acme": "アクメ"},\n'
            '"header_backbone": {"slide1_shape0": "四半期業績レ'  # cut off here
        )
        with patch.object(contract_mod, "_complete", return_value=truncated):
            result = build_contract(_deck(40), "en", "ja", api_key="x")
        self.assertFalse(is_empty_contract(result))
        self.assertEqual(result["glossary"]["Revenue"], "売上")
        self.assertEqual(result["proper_nouns"]["Acme"], {"canonical": "アクメ"})
        self.assertEqual(result["register"]["style"], "teineigo (です・ます)")

    def test_degrades_to_empty_on_api_error(self):
        with patch.object(contract_mod, "_complete", side_effect=RuntimeError("429")):
            result = build_contract(_deck(10), "en", "ja", api_key="x")
        self.assertTrue(is_empty_contract(result))

    def test_disabled_flag_short_circuits(self):
        with patch.object(contract_mod.config, "CONTRACT_ENABLED", False):
            with patch.object(contract_mod, "_complete") as m:
                result = build_contract(_deck(50), "en", "ja", api_key="x")
        m.assert_not_called()
        self.assertEqual(result, EMPTY_CONTRACT)


class TestFormatContract(unittest.TestCase):
    def test_empty_contract_renders_empty_string(self):
        self.assertEqual(format_contract(EMPTY_CONTRACT), "")
        self.assertEqual(format_contract({}), "")

    def test_rendered_block_contains_locked_decisions(self):
        rendered = format_contract(
            contract_mod._validate_contract(SAMPLE_CONTRACT_JSON)
        )
        self.assertIn("COHERENCE CONTRACT", rendered)
        self.assertIn("Revenue -> 売上", rendered)
        self.assertIn("当社", rendered)
        self.assertIn("マイクロソフト", rendered)
        self.assertIn("ミクロソフト", rendered)  # forbidden variant surfaced
        self.assertIn("体言止め", rendered)
        self.assertIn("slide1_shape0", rendered)


class TestEnrichBlocks(unittest.TestCase):
    def test_roles_from_metadata_and_id_patterns(self):
        text_dict = {
            "presentation_title": "Deck",
            "slide1_shape0": "Big Title",
            "slide1_shape1_p0": "A bullet",
            "slide2_shape3_table_r0c0": "Header cell",
            "slide2_shape3_table_r1c0": "Body cell",
            "slide3_notes": "Speaker note",
        }
        slide_metadata = [
            {
                "id": "presentation_title",
                "type": "presentation_title",
                "slide_number": 0,
            },
            {
                "slide_number": 1,
                "elements": [
                    {"id": "slide1_shape0", "type": "shape", "role": "title"},
                    {
                        "id": "slide1_shape1_p0",
                        "type": "shape_paragraph",
                        "role": "body_bullet",
                    },
                ],
            },
        ]
        enriched = enrich_blocks(text_dict, slide_metadata)
        self.assertEqual(enriched["presentation_title"]["role"], "title")
        self.assertEqual(enriched["slide1_shape0"]["role"], "title")
        self.assertEqual(enriched["slide1_shape1_p0"]["role"], "body_bullet")
        self.assertEqual(enriched["slide2_shape3_table_r0c0"]["role"], "table_header")
        self.assertEqual(enriched["slide2_shape3_table_r1c0"]["role"], "table_cell")
        self.assertEqual(enriched["slide3_notes"]["role"], "speaker_note")
        # reading_order is the extraction order.
        self.assertEqual(enriched["presentation_title"]["reading_order"], 0)
        self.assertEqual(enriched["slide3_notes"]["reading_order"], 5)
        # slide numbers parsed from ids when not in metadata.
        self.assertEqual(enriched["slide2_shape3_table_r0c0"]["slide_number"], 2)

    def test_degrades_without_metadata_native_slides(self):
        # Native Slides passes no slide_metadata; table cells use the "__r" separator.
        text_dict = {"abc123": "A shape", "abc123__r0c0": "H", "abc123__r1c1": "v"}
        enriched = enrich_blocks(text_dict, [])
        self.assertEqual(enriched["abc123"]["role"], "body_bullet")
        self.assertEqual(enriched["abc123__r0c0"]["role"], "table_header")
        self.assertEqual(enriched["abc123__r1c1"]["role"], "table_cell")


class TestEstimateOutputTokens(unittest.TestCase):
    def test_scales_with_content(self):
        small = estimate_output_tokens({"a": "x" * 100})
        big = estimate_output_tokens({f"k{i}": "x" * 100 for i in range(20)})
        self.assertGreater(big, small)


if __name__ == "__main__":
    unittest.main()
