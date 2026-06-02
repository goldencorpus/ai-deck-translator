"""Phase 4 worker tests — native Google Slides fulfillment + preview (mocked services)."""

import asyncio
import base64
import os

os.environ.setdefault("CLAUDE_API_KEY", "test-dummy")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-dummy")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "cid")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "secret")
os.environ.setdefault(
    "GOOGLE_TOKEN_ENC_KEY", base64.b64encode(os.urandom(32)).decode()
)

from unittest import mock

import worker.app as app
import worker.preview as preview
from ai_deck_translator.utils.exceptions import (
    AuthenticationError,
    IncompleteTranslationError,
)


def run(coro):
    return asyncio.run(coro)


JOB = {
    "id": "j1",
    "user_id": "u1",
    "source_format": "gslides",
    "google_file_id": "FILE_1",
    "google_refresh_token": "v1:a:b:c",
    "source_lang": "auto",
    "target_lang": "ja",
    "stripe_payment_intent_id": "pi_1",
}


# ---- _extract_first_slide -------------------------------------------------------------
def test_extract_first_slide_only():
    presentation = {
        "slides": [
            {
                "objectId": "p1",
                "pageElements": [
                    {
                        "objectId": "o1",
                        "shape": {
                            "text": {"textElements": [{"textRun": {"content": "Hello"}}]}
                        },
                    }
                ],
            },
            {
                "objectId": "p2",
                "pageElements": [
                    {
                        "objectId": "o2",
                        "shape": {
                            "text": {
                                "textElements": [{"textRun": {"content": "Second"}}]
                            }
                        },
                    }
                ],
            },
        ]
    }
    page_id, text = preview._extract_first_slide(presentation)
    assert page_id == "p1"
    assert text == {"o1": "Hello"}  # slide 2's "Second" is excluded


def test_extract_first_slide_empty():
    assert preview._extract_first_slide({"slides": []}) == (None, {})


# ---- make_gslides_preview -------------------------------------------------------------
def _fake_services():
    slides = mock.MagicMock()
    slides.presentations().get().execute.return_value = {
        "title": "Deck",
        "slides": [
            {
                "objectId": "p1",
                "pageElements": [
                    {
                        "objectId": "o1",
                        "shape": {
                            "text": {"textElements": [{"textRun": {"content": "Hi"}}]}
                        },
                    }
                ],
            }
        ],
    }
    slides.presentations().batchUpdate().execute.return_value = {}
    slides.presentations().pages().getThumbnail().execute.return_value = {
        "contentUrl": "https://example.com/thumb.png"
    }
    drive = mock.MagicMock()
    drive.files().copy().execute.return_value = {"id": "COPY_1"}
    return slides, drive


def test_make_gslides_preview_translates_copies_and_trashes(tmp_path):
    slides, drive = _fake_services()
    with mock.patch.object(
        preview, "translate_text", return_value={"o1": "こんにちは"}
    ), mock.patch.object(
        preview.urllib.request, "urlretrieve"
    ) as url, mock.patch.object(
        preview, "watermark"
    ) as wm:
        # Simulate the download + watermark producing files.
        url.side_effect = lambda u, p: open(p, "wb").write(b"png")
        wm.side_effect = lambda src, out: open(out, "wb").write(b"wm")
        out = preview.make_gslides_preview(
            "FILE_1", "auto", "ja", str(tmp_path), slides, drive
        )
    assert out.endswith("preview.png")
    # Translated slide 1 was written back to the COPY (not the original).
    assert slides.presentations().batchUpdate.called
    # The transient copy is always trashed.
    drive.files().delete.assert_called_with(fileId="COPY_1")


# ---- _process_gslides happy path ------------------------------------------------------
def _patches(native_side=None, native_return=("NEW", "https://docs.google.com/x/edit")):
    native = mock.patch.object(
        app,
        "translate_presentation_native",
        side_effect=native_side,
        return_value=None if native_side else native_return,
    )
    return native


def test_process_gslides_success():
    with mock.patch.object(
        app, "decrypt_token", return_value="refresh"
    ), mock.patch.object(
        app, "build_services_from_refresh_token", return_value=("S", "D")
    ), mock.patch.object(
        app,
        "translate_presentation_native",
        return_value=("NEW", "https://docs.google.com/presentation/d/NEW/edit"),
    ), mock.patch.object(
        app, "_update_job", new_callable=mock.AsyncMock
    ) as update, mock.patch.object(
        app, "_user_email", new_callable=mock.AsyncMock, return_value="a@b.com"
    ), mock.patch.object(
        app, "_send_email", new_callable=mock.AsyncMock
    ) as semail, mock.patch.object(
        app, "_stripe_refund", new_callable=mock.AsyncMock
    ) as refund:
        run(app._process_gslides(mock.MagicMock(), JOB))

    fields = update.call_args.args[2]
    assert fields["status"] == "completed"
    assert fields["output_edit_url"].endswith("/edit")
    assert fields["google_refresh_token"] is None  # zero-retention on success
    refund.assert_not_awaited()
    semail.assert_awaited()
    # delivery email carries the edit link
    assert "Open it in Google Slides" in semail.call_args.args[3]


def _run_failure(native_side):
    captured = {}
    with mock.patch.object(
        app, "decrypt_token", return_value="refresh"
    ), mock.patch.object(
        app, "build_services_from_refresh_token", return_value=("S", "D")
    ), mock.patch.object(
        app, "translate_presentation_native", side_effect=native_side
    ), mock.patch.object(
        app, "_update_job", new_callable=mock.AsyncMock
    ) as update, mock.patch.object(
        app, "_user_email", new_callable=mock.AsyncMock, return_value="a@b.com"
    ), mock.patch.object(
        app, "_send_email", new_callable=mock.AsyncMock
    ) as semail, mock.patch.object(
        app, "_stripe_refund", new_callable=mock.AsyncMock
    ) as refund:
        run(app._process_gslides(mock.MagicMock(), JOB))
        captured["fields"] = update.call_args.args[2]
        captured["subject"] = semail.call_args.args[2]
        captured["refund"] = refund
    return captured


def test_process_gslides_gate_failure_refunds_with_completeness_msg():
    c = _run_failure(IncompleteTranslationError("2/10 blocks missing", ["x"], 10))
    assert c["fields"]["status"] == "failed"
    assert c["fields"]["google_refresh_token"] is None  # zero-retention on failure
    c["refund"].assert_awaited()  # no-HITL guarantee
    assert "completeness check" in c["subject"].lower() or "didn't complete" in c[
        "subject"
    ].lower()


def test_process_gslides_auth_failure_says_lost_access():
    c = _run_failure(AuthenticationError("refresh token revoked"))
    assert c["fields"]["status"] == "failed"
    c["refund"].assert_awaited()  # still refunds
    assert "lost access" in c["subject"].lower()


def test_process_gslides_http_403_classified_as_access_loss():
    class FakeResp:
        status = 403

    class FakeHttpError(Exception):
        resp = FakeResp()

    c = _run_failure(FakeHttpError("permission denied"))
    c["refund"].assert_awaited()
    assert "lost access" in c["subject"].lower()


def test_process_gslides_generic_failure_refunds():
    c = _run_failure(RuntimeError("boom"))
    assert c["fields"]["status"] == "failed"
    c["refund"].assert_awaited()
