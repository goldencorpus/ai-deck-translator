"""
Tests for the native Google Slides path — focused on the SaaS additions:
injected per-user services and cleanup-on-failure. The translation engine itself
is mocked; these assert the auth seam and the failure-cleanup contract.
"""

import unittest
from unittest.mock import MagicMock, patch

from ai_deck_translator.core import native_slides
from ai_deck_translator.utils.exceptions import IncompleteTranslationError


def _fake_services(text_dict):
    """Build mock slides+drive services for a one-shape deck."""
    slides_service = MagicMock()
    slides_service.presentations().get().execute.return_value = {
        "title": "Deck",
        "slides": [
            {
                "pageElements": [
                    {
                        "objectId": obj_id,
                        "shape": {
                            "text": {"textElements": [{"textRun": {"content": text}}]}
                        },
                    }
                    for obj_id, text in text_dict.items()
                ]
            }
        ],
    }
    slides_service.presentations().batchUpdate().execute.return_value = {}
    drive_service = MagicMock()
    drive_service.files().copy().execute.return_value = {"id": "COPY_ID"}
    return slides_service, drive_service


class TestNativeSlidesInjectedServices(unittest.TestCase):
    @patch("ai_deck_translator.core.native_slides.authenticate_google")
    @patch("ai_deck_translator.core.native_slides.translate_text")
    def test_injected_services_skip_authenticate_google(
        self, mock_translate, mock_auth
    ):
        slides_service, drive_service = _fake_services({"o1": "Hello"})
        mock_translate.return_value = {"o1": "こんにちは"}

        new_id, edit_url = native_slides.translate_presentation_native(
            "SRC_ID",
            target_language="ja",
            slides_service=slides_service,
            drive_service=drive_service,
        )

        mock_auth.assert_not_called()  # acted as the injected (per-user) identity
        self.assertEqual(new_id, "COPY_ID")
        self.assertIn("COPY_ID", edit_url)
        self.assertTrue(slides_service.presentations().batchUpdate.called)

    @patch("ai_deck_translator.core.native_slides.authenticate_google")
    @patch("ai_deck_translator.core.native_slides.translate_text")
    def test_missing_blocks_trip_gate_and_cleanup(self, mock_translate, mock_auth):
        slides_service, drive_service = _fake_services({"o1": "Hello", "o2": "World"})
        mock_translate.return_value = {"o1": "こんにちは"}  # o2 missing → gate trips

        with self.assertRaises(IncompleteTranslationError):
            native_slides.translate_presentation_native(
                "SRC_ID",
                slides_service=slides_service,
                drive_service=drive_service,
                cleanup_on_failure=True,
            )

        drive_service.files().delete.assert_called_with(fileId="COPY_ID")

    @patch("ai_deck_translator.core.native_slides.authenticate_google")
    @patch("ai_deck_translator.core.native_slides.translate_text")
    def test_no_cleanup_when_flag_false(self, mock_translate, mock_auth):
        slides_service, drive_service = _fake_services({"o1": "Hello", "o2": "World"})
        mock_translate.return_value = {"o1": "こんにちは"}

        with self.assertRaises(IncompleteTranslationError):
            native_slides.translate_presentation_native(
                "SRC_ID",
                slides_service=slides_service,
                drive_service=drive_service,
                cleanup_on_failure=False,
            )

        drive_service.files().delete.assert_not_called()  # CLI keeps copy for inspection


class TestBuildServicesFromRefreshToken(unittest.TestCase):
    def test_missing_token_raises(self):
        from ai_deck_translator.auth.google_auth import (
            build_services_from_refresh_token,
        )
        from ai_deck_translator.utils.exceptions import AuthenticationError

        with self.assertRaises(AuthenticationError):
            build_services_from_refresh_token("", "cid", "secret")

    @patch("ai_deck_translator.auth.google_auth.build")
    @patch("ai_deck_translator.auth.google_auth.Credentials")
    def test_refreshes_and_builds_services(self, mock_creds_cls, mock_build):
        from ai_deck_translator.auth.google_auth import (
            build_services_from_refresh_token,
        )

        creds = MagicMock()
        mock_creds_cls.return_value = creds

        slides, drive = build_services_from_refresh_token("rtok", "cid", "secret")

        creds.refresh.assert_called_once()  # minted a fresh access token
        self.assertEqual(mock_build.call_count, 2)  # slides + drive


if __name__ == "__main__":
    unittest.main()
