"""
Security regression tests for the web UI (no `openai` dependency, so they always run —
unlike test_web.py, which is skipped when the optional openai package is absent).

Covers:
- SECRET_KEY must be required in production (no hardcoded "dev_key" fallback).
- /download must never serve a file outside the upload folder or belonging to another
  session (path traversal / cross-session leak).
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from ai_deck_translator.web.app import create_app, translation_state


class TestSecretKeyGuard(unittest.TestCase):
    def test_requires_secret_key_in_production(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SECRET_KEY", None)
            with self.assertRaises(RuntimeError):
                create_app(debug=False)

    def test_debug_uses_ephemeral_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SECRET_KEY", None)
            app = create_app(debug=True)
            self.assertTrue(app.config["SECRET_KEY"])
            self.assertNotEqual(app.config["SECRET_KEY"], "dev_key")


class TestDownloadScope(unittest.TestCase):
    def setUp(self):
        self.app = create_app(debug=True)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        translation_state.clear()

    def _set_session(self, session_id):
        with self.client.session_transaction() as sess:
            sess["session_id"] = session_id

    def test_refuses_file_outside_upload_folder(self):
        self._set_session("sessA")
        evil = tempfile.NamedTemporaryFile(suffix="_x.pptx", delete=False)
        evil.write(b"x")
        evil.close()
        try:
            translation_state["sessA"] = {
                "status": "completed",
                "output_file": evil.name,  # outside UPLOAD_FOLDER
                "progress": 1,
                "total": 1,
            }
            resp = self.client.get("/download")
            self.assertIn(resp.status_code, (301, 302))  # redirected, not served
        finally:
            os.unlink(evil.name)

    def test_refuses_other_sessions_file(self):
        self._set_session("sessA")
        upload = self.app.config["UPLOAD_FOLDER"]
        other = os.path.join(upload, "sessB_deck.pptx")  # different session prefix
        with open(other, "wb") as f:
            f.write(b"x")
        try:
            translation_state["sessA"] = {
                "status": "completed",
                "output_file": other,
                "progress": 1,
                "total": 1,
            }
            resp = self.client.get("/download")
            self.assertIn(resp.status_code, (301, 302))
        finally:
            os.unlink(other)


if __name__ == "__main__":
    unittest.main()
