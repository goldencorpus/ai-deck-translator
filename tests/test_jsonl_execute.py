"""
Deterministic tests for the P1 "execute" pass: JSONL parsing, JSONL output + prompt caching
in translate_batch, and seed-then-fan-out concurrency in translate_text. All API-free.
"""

import unittest
from unittest.mock import patch, MagicMock

from ai_deck_translator.pptx.jsonl import (
    parse_jsonl_translations,
    has_end_sentinel,
    END_SENTINEL,
)
from ai_deck_translator.pptx import translator as pptx_translator
from ai_deck_translator.pptx.translator import translate_batch, translate_text


class TestJsonlParser(unittest.TestCase):
    def test_parses_well_formed_stream(self):
        stream = (
            '{"id": "slide1_shape0", "t": "タイトル"}\n'
            '{"id": "slide1_shape1", "t": "本文"}\n'
            '{"id": "__END__"}'
        )
        self.assertEqual(
            parse_jsonl_translations(stream),
            {"slide1_shape0": "タイトル", "slide1_shape1": "本文"},
        )
        self.assertTrue(has_end_sentinel(stream))

    def test_truncated_tail_keeps_complete_records(self):
        # Last line is cut off mid-record (max_tokens) — keep the two that arrived.
        stream = (
            '{"id": "a", "t": "alpha"}\n'
            '{"id": "b", "t": "beta"}\n'
            '{"id": "c", "t": "gam'
        )
        result = parse_jsonl_translations(stream)
        self.assertEqual(result, {"a": "alpha", "b": "beta"})
        self.assertFalse(has_end_sentinel(stream))

    def test_tolerates_fences_brackets_and_trailing_commas(self):
        stream = (
            "```json\n"
            "[\n"
            '{"id": "a", "t": "x"},\n'
            '{"id": "b", "t": "y"},\n'
            "]\n"
            "```"
        )
        self.assertEqual(parse_jsonl_translations(stream), {"a": "x", "b": "y"})

    def test_escaped_newline_in_value_preserved(self):
        stream = '{"id": "a", "t": "line1\\nline2"}'
        self.assertEqual(parse_jsonl_translations(stream), {"a": "line1\nline2"})

    def test_empty_and_none(self):
        self.assertEqual(parse_jsonl_translations(""), {})
        self.assertEqual(parse_jsonl_translations(None), {})


def _mock_response(text, *, cache_read=0, cache_write=0, stop_reason="end_turn"):
    resp = MagicMock()
    content = MagicMock()
    content.text = text
    resp.content = [content]
    resp.stop_reason = stop_reason
    resp.usage = MagicMock(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_write,
    )
    return resp


class TestTranslateBatchJsonl(unittest.TestCase):
    @patch("anthropic.Anthropic")
    def test_parses_jsonl_and_marks_cache_prefix(self, mock_anthropic):
        client = MagicMock()
        mock_anthropic.return_value = client
        client.messages.create.return_value = _mock_response(
            '{"id": "obj1", "t": "T1"}\n{"id": "obj2", "t": "T2"}\n{"id": "__END__"}',
            cache_write=200,
        )

        cost = {}
        with patch.object(pptx_translator.config, "PROMPT_CACHE", True):
            result = translate_batch(
                {"obj1": "o1", "obj2": "o2"},
                0,
                [],
                "en",
                "ja",
                api_key="k",
                cost_tracker=cost,
                glossary="== COHERENCE CONTRACT ==\nRevenue -> 売上\n==",
            )

        self.assertEqual(result, {"obj1": "T1", "obj2": "T2"})
        # System param is a cache-marked content-block list, and the contract rode along in it.
        call = client.messages.create.call_args[1]
        system = call["system"]
        self.assertIsInstance(system, list)
        self.assertEqual(system[0]["cache_control"], {"type": "ephemeral"})
        self.assertIn("COHERENCE CONTRACT", system[0]["text"])
        # User message carries only the per-batch content (after the cache breakpoint).
        self.assertNotIn("COHERENCE CONTRACT", call["messages"][0]["content"])
        self.assertEqual(cost["cache_write_tokens"], 200)

    @patch("anthropic.Anthropic")
    def test_truncated_batch_returns_partial(self, mock_anthropic):
        client = MagicMock()
        mock_anthropic.return_value = client
        client.messages.create.return_value = _mock_response(
            '{"id": "obj1", "t": "T1"}\n{"id": "obj2", "t": "tru',
            stop_reason="max_tokens",
        )
        result = translate_batch(
            {"obj1": "o1", "obj2": "o2"}, 0, [], "en", "ja", api_key="k"
        )
        # Partial accepted; obj2 absent so the caller's retry pass can recover it.
        self.assertEqual(result, {"obj1": "T1"})

    @patch("anthropic.Anthropic")
    def test_falls_back_to_single_json_object(self, mock_anthropic):
        client = MagicMock()
        mock_anthropic.return_value = client
        client.messages.create.return_value = _mock_response(
            '{"obj1": "T1", "obj2": "T2"}'  # legacy single-object format
        )
        result = translate_batch(
            {"obj1": "o1", "obj2": "o2"}, 0, [], "en", "ja", api_key="k"
        )
        self.assertEqual(result, {"obj1": "T1", "obj2": "T2"})

    @patch("anthropic.Anthropic")
    def test_no_cache_uses_plain_system_string(self, mock_anthropic):
        client = MagicMock()
        mock_anthropic.return_value = client
        client.messages.create.return_value = _mock_response('{"id": "a", "t": "x"}')
        with patch.object(pptx_translator.config, "PROMPT_CACHE", False):
            translate_batch({"a": "o"}, 0, [], "en", "ja", api_key="k")
        self.assertIsInstance(
            client.messages.create.call_args[1]["system"], str
        )


class TestSeedThenFanOut(unittest.TestCase):
    def test_all_batches_covered_seed_runs_first(self):
        # 100 unique blocks, 10 per batch -> 10 batches -> seed + 9-way fan-out.
        text_dict = {f"slide1_shape{i}": f"src {i}" for i in range(100)}

        order = []
        order_lock = __import__("threading").Lock()

        def fake_batch(batch, batch_index, *a, **k):
            with order_lock:
                order.append(batch_index)
            return {bid: f"[ja] {v}" for bid, v in batch.items()}

        with patch.object(pptx_translator.config, "PROMPT_CACHE", True), patch.object(
            pptx_translator.config, "BLOCKS_PER_BATCH", 10
        ), patch.object(
            pptx_translator, "build_contract", return_value={}
        ), patch.object(
            pptx_translator, "translate_batch", side_effect=fake_batch
        ):
            result = translate_text(text_dict, [], "en", "ja")

        # Every block translated (completeness preserved through the parallel path).
        self.assertEqual(len(result), 100)
        for bid, src in text_dict.items():
            self.assertEqual(result[bid], f"[ja] {src}")
        # The seed (batch 0) was dispatched before the fan-out completed.
        self.assertEqual(order[0], 0)
        self.assertEqual(sorted(order), list(range(10)))


if __name__ == "__main__":
    unittest.main()
