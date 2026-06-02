"""
Decktr VPS worker — async fulfillment for the no-HITL SaaS.

Runs on the GC VPS (python-pptx can't run on Supabase Edge Functions). The Next.js app
(`decktr-web`) creates a `jobs` row (status=pending), uploads the input deck to Supabase
Storage, and fires a forget-and-go `POST /run {job_id}` here. This service:

  1. authenticates the trigger (bearer shared secret)
  2. atomically CLAIMS the job (UPDATE ... WHERE status='pending') — idempotent, so a retried
     trigger or the stale-job watchdog re-trigger never double-runs it
  3. downloads the input deck from Storage (service role)
  4. runs the hardened engine: translate_pptx (contract -> execute -> verify -> gate)
  5. uploads the output, updates the job (status/slide_count/cost), DELETES the input (zero-retention)
  6. on IncompleteTranslationError (the 100%-or-fail-loud gate) -> status=failed + Stripe auto-refund

Concurrency: a bounded pool (WORKER_CONCURRENCY, default 2) drains claimed jobs; after each
completion it drains any backlog of `pending` jobs (handles bursts under pure fire-and-forget).

STATUS: step-1 skeleton. The engine call (translate_pptx) is real; the Supabase/Stripe I/O
helpers are implemented against their REST APIs but are wired + verified end-to-end in step 2.
Env (set on the VPS, never committed): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
WORKER_SHARED_SECRET, STRIPE_SECRET_KEY, CLAUDE_API_KEY, WORKER_CONCURRENCY.
"""

from __future__ import annotations  # PEP 604 unions (dict | None) — VPS runs Python 3.9

import asyncio
import os
import tempfile

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from ai_deck_translator.auth.google_auth import build_services_from_refresh_token
from ai_deck_translator.core.native_slides import translate_presentation_native
from ai_deck_translator.pptx.translator import translate_pptx
from ai_deck_translator.utils.exceptions import (
    AuthenticationError,
    IncompleteTranslationError,
    NetworkError,
)
from worker.preview import make_gslides_preview, make_preview
from worker.token_crypto import decrypt_token

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SHARED_SECRET = os.environ.get("WORKER_SHARED_SECRET", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
WORKER_CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "2"))
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "SlideVerso <noreply@slideverso.com>")
APP_URL = os.environ.get("APP_URL", "https://slideverso.com")
# Google Slides (native) — per-customer OAuth. GOOGLE_TOKEN_ENC_KEY is read inside
# worker.token_crypto. These two must match the values the Next.js app uses.
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")

INPUT_BUCKET = "deck-input"
OUTPUT_BUCKET = "deck-output"

app = FastAPI(title="slideverso-worker")
_semaphore = asyncio.Semaphore(WORKER_CONCURRENCY)


class RunRequest(BaseModel):
    job_id: str


def _sb_headers() -> dict:
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }


async def _claim_job(client: httpx.AsyncClient, job_id: str) -> dict | None:
    """Atomically claim a pending job. Returns the row if WE claimed it, else None."""
    resp = await client.patch(
        f"{SUPABASE_URL}/rest/v1/jobs",
        params={"id": f"eq.{job_id}", "status": "eq.pending"},
        headers={**_sb_headers(), "Prefer": "return=representation"},
        json={"status": "processing", "started_at": "now()"},
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


async def _update_job(client: httpx.AsyncClient, job_id: str, fields: dict) -> None:
    resp = await client.patch(
        f"{SUPABASE_URL}/rest/v1/jobs",
        params={"id": f"eq.{job_id}"},
        headers=_sb_headers(),
        json=fields,
    )
    resp.raise_for_status()


async def _storage_download(client: httpx.AsyncClient, path: str, dest: str) -> None:
    resp = await client.get(
        f"{SUPABASE_URL}/storage/v1/object/{INPUT_BUCKET}/{path}",
        headers={"Authorization": f"Bearer {SERVICE_KEY}"},
    )
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)


async def _storage_upload(client: httpx.AsyncClient, path: str, src: str) -> None:
    with open(src, "rb") as f:
        data = f.read()
    resp = await client.post(
        f"{SUPABASE_URL}/storage/v1/object/{OUTPUT_BUCKET}/{path}",
        headers={
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "x-upsert": "true",
        },
        content=data,
    )
    resp.raise_for_status()


async def _storage_delete_input(client: httpx.AsyncClient, path: str) -> None:
    """Zero-retention: delete the uploaded source deck as soon as we've consumed it."""
    await client.request(
        "DELETE",
        f"{SUPABASE_URL}/storage/v1/object/{INPUT_BUCKET}/{path}",
        headers={"Authorization": f"Bearer {SERVICE_KEY}"},
    )


async def _user_email(client: httpx.AsyncClient, user_id: str) -> str | None:
    resp = await client.get(
        f"{SUPABASE_URL}/rest/v1/profiles",
        params={"id": f"eq.{user_id}", "select": "email"},
        headers=_sb_headers(),
    )
    if resp.status_code != 200:
        return None
    rows = resp.json()
    return rows[0].get("email") if rows else None


async def _send_email(
    client: httpx.AsyncClient, to: str | None, subject: str, html: str
) -> None:
    """Best-effort transactional email via Resend. Never raises into the job flow."""
    if not (RESEND_API_KEY and to):
        return
    try:
        await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html},
        )
    except Exception:  # noqa: BLE001 — email must never break fulfillment
        pass


async def _stripe_refund(client: httpx.AsyncClient, payment_intent_id: str) -> None:
    """Auto-refund on gate-failure — the no-HITL guarantee, enforced in code."""
    if not (STRIPE_SECRET_KEY and payment_intent_id):
        return
    await client.post(
        "https://api.stripe.com/v1/refunds",
        headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
        data={"payment_intent": payment_intent_id},
    )


async def _process(job_id: str) -> None:
    """Claim + run one job end-to-end. Safe to call multiple times (claim is idempotent)."""
    async with _semaphore, httpx.AsyncClient(timeout=900) as client:
        job = await _claim_job(client, job_id)
        if not job:
            return  # already claimed / not pending — idempotent no-op

        if job.get("source_format") == "gslides":
            await _process_gslides(client, job)
            return

        input_path = job.get("input_storage_path")
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "input.pptx")
            out = os.path.join(tmp, "output.pptx")
            try:
                await _storage_download(client, input_path, src)
                # The engine is synchronous + CPU/IO heavy — run it off the event loop.
                await asyncio.to_thread(
                    translate_pptx,
                    src,
                    out,
                    job.get("source_lang", "en"),
                    job.get("target_lang", "ja"),
                )
                output_path = f"{job['user_id']}/{job_id}/output.pptx"
                await _storage_upload(client, output_path, out)
                await _update_job(
                    client,
                    job_id,
                    {
                        "status": "completed",
                        "progress": 100,
                        "output_storage_path": output_path,
                        "completed_at": "now()",
                    },
                )
                await _send_email(
                    client,
                    await _user_email(client, job["user_id"]),
                    "Your translated deck is ready",
                    f"<p>Your deck is translated and ready — every slide complete and consistent.</p>"
                    f'<p><a href="{APP_URL}/app/job/{job_id}">Download it from your dashboard</a>.</p>'
                    f"<p>— Golden Corpus</p>",
                )
            except IncompleteTranslationError as exc:
                # 100%-or-fail-loud gate tripped — never ship a partial deck; refund.
                await _update_job(
                    client,
                    job_id,
                    {
                        "status": "failed",
                        "error_message": str(exc)[:500],
                        "completed_at": "now()",
                    },
                )
                await _stripe_refund(client, job.get("stripe_payment_intent_id"))
                await _send_email(
                    client,
                    await _user_email(client, job["user_id"]),
                    "Your translation didn't complete — you've been refunded",
                    f"<p>Your deck didn't pass our completeness check, so we didn't deliver it — "
                    f"and you've been automatically refunded.</p>"
                    f'<p>Sorry about that. You can try again at <a href="{APP_URL}/app">slideverso.com</a>.</p>'
                    f"<p>— Golden Corpus</p>",
                )
            except (
                Exception
            ) as exc:  # noqa: BLE001 — any failure must refund, never strand
                await _update_job(
                    client,
                    job_id,
                    {
                        "status": "failed",
                        "error_message": str(exc)[:500],
                        "completed_at": "now()",
                    },
                )
                await _stripe_refund(client, job.get("stripe_payment_intent_id"))
                await _send_email(
                    client,
                    await _user_email(client, job["user_id"]),
                    "Your translation didn't complete — you've been refunded",
                    f"<p>Your deck didn't pass our completeness check, so we didn't deliver it — "
                    f"and you've been automatically refunded.</p>"
                    f'<p>Sorry about that. You can try again at <a href="{APP_URL}/app">slideverso.com</a>.</p>'
                    f"<p>— Golden Corpus</p>",
                )
            finally:
                if input_path:
                    await _storage_delete_input(client, input_path)  # zero-retention


async def _process_gslides(client: httpx.AsyncClient, job: dict) -> None:
    """Translate a Google Slides deck natively, as the customer (their refresh token).

    Nothing of theirs is in our storage — the translated copy lands in their own Drive and
    we deliver an edit link. The encrypted refresh token is the single customer credential
    we hold; it is NULLed on EVERY terminal state (success and all failures) below.
    """
    job_id = job["id"]
    file_id = job.get("google_file_id")
    enc = job.get("google_refresh_token")
    try:
        if not (file_id and enc):
            raise RuntimeError("gslides job missing google_file_id / refresh token")
        refresh = decrypt_token(enc)
        slides_service, drive_service = await asyncio.to_thread(
            build_services_from_refresh_token,
            refresh,
            GOOGLE_OAUTH_CLIENT_ID,
            GOOGLE_OAUTH_CLIENT_SECRET,
        )
        _new_id, edit_url = await asyncio.to_thread(
            translate_presentation_native,
            file_id,
            job.get("source_lang", "auto"),
            job.get("target_lang", "ja"),
            None,  # api_key (engine reads its own .env CLAUDE_API_KEY)
            None,  # progress_callback
            slides_service,
            drive_service,
            True,  # cleanup_on_failure — trash the partial copy for a refunded customer
        )
        await _update_job(
            client,
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "output_edit_url": edit_url,
                "google_refresh_token": None,  # zero-retention: drop the credential now
                "completed_at": "now()",
            },
        )
        await _send_email(
            client,
            await _user_email(client, job["user_id"]),
            "Your translated deck is ready",
            f"<p>Your Google Slides deck is translated — every slide complete and "
            f"consistent.</p>"
            f'<p><a href="{edit_url}">Open it in Google Slides</a>. The translated copy is '
            f"in your own Google Drive; we keep nothing.</p>"
            f"<p>— Golden Corpus</p>",
        )
    except IncompleteTranslationError as exc:
        await _fail_gslides(client, job, str(exc), cause="gate")
    except (AuthenticationError, NetworkError) as exc:
        await _fail_gslides(client, job, str(exc), cause="google")
    except Exception as exc:  # noqa: BLE001 — any failure must refund, never strand
        # A googleapiclient HttpError (revoked grant / file moved) usually lands here; a
        # 401/403/404 means we lost access to the file rather than a generic engine fault.
        status = getattr(getattr(exc, "resp", None), "status", None)
        cause = "google" if status in (401, 403, 404) else "generic"
        await _fail_gslides(client, job, str(exc), cause=cause)


async def _fail_gslides(
    client: httpx.AsyncClient, job: dict, msg: str, cause: str
) -> None:
    """Mark a gslides job failed, NULL its credential, refund, and email the right reason.

    All three causes still auto-refund — the no-HITL guarantee is unchanged; only the
    message differs (the generic 'completeness check' wording is wrong when we simply lost
    access to the user's file)."""
    await _update_job(
        client,
        job["id"],
        {
            "status": "failed",
            "error_message": msg[:500],
            "google_refresh_token": None,  # zero-retention even on failure
            "completed_at": "now()",
        },
    )
    await _stripe_refund(client, job.get("stripe_payment_intent_id"))

    if cause == "google":
        subject = "We lost access to your Google file — you've been refunded"
        html = (
            "<p>We couldn’t finish translating your deck because we lost access to your "
            "Google Slides file — this usually means access was revoked, or the file was "
            "moved or deleted before we ran.</p>"
            "<p>You’ve been automatically refunded. You can reconnect and try again at "
            f'<a href="{APP_URL}/app">slideverso.com</a>.</p>'
            "<p>— Golden Corpus</p>"
        )
    elif cause == "gate":
        subject = "Your translation didn't complete — you've been refunded"
        html = (
            "<p>Your deck didn’t pass our completeness check, so we didn’t deliver it — "
            "and you’ve been automatically refunded.</p>"
            f'<p>Sorry about that. You can try again at <a href="{APP_URL}/app">'
            "slideverso.com</a>.</p>"
            "<p>— Golden Corpus</p>"
        )
    else:
        subject = "Your translation didn't complete — you've been refunded"
        html = (
            "<p>Something went wrong translating your deck, so we didn’t deliver it — and "
            "you’ve been automatically refunded.</p>"
            f'<p>Sorry about that. You can try again at <a href="{APP_URL}/app">'
            "slideverso.com</a>.</p>"
            "<p>— Golden Corpus</p>"
        )
    await _send_email(client, await _user_email(client, job["user_id"]), subject, html)


@app.post("/run", status_code=202)
async def run(req: RunRequest, authorization: str = Header(default="")):
    if not SHARED_SECRET or authorization != f"Bearer {SHARED_SECRET}":
        raise HTTPException(status_code=401, detail="unauthorized")
    # Fire-and-forget: schedule processing, return 202 immediately (MWT pattern).
    asyncio.create_task(_process(req.job_id))
    return {"accepted": req.job_id}


async def _upload_preview_png(
    client: httpx.AsyncClient, user_id: str, job_id: str, png_path: str
) -> None:
    """Upload a rendered preview PNG to output storage and point the job at it."""
    preview_path = f"{user_id}/{job_id}/preview.png"
    with open(png_path, "rb") as f:
        data = f.read()
    up = await client.post(
        f"{SUPABASE_URL}/storage/v1/object/{OUTPUT_BUCKET}/{preview_path}",
        headers={
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "image/png",
            "x-upsert": "true",
        },
        content=data,
    )
    up.raise_for_status()
    await _update_job(client, job_id, {"preview_storage_path": preview_path})


async def _preview(job_id: str) -> None:
    """Generate the free watermarked preview for an unpaid job (pre-payment proof).
    Neither the input deck nor (for gslides) the refresh token is dropped here — both are
    still needed for the paid translation; the credential is only NULLed on terminal states.
    """
    async with _semaphore, httpx.AsyncClient(timeout=600) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/jobs",
            params={
                "id": f"eq.{job_id}",
                "select": (
                    "id,user_id,source_format,input_storage_path,source_lang,"
                    "target_lang,google_file_id,google_refresh_token"
                ),
            },
            headers=_sb_headers(),
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return
        job = rows[0]

        if job.get("source_format") == "gslides":
            file_id = job.get("google_file_id")
            enc = job.get("google_refresh_token")
            if not (file_id and enc):
                return
            refresh = decrypt_token(enc)
            slides_service, drive_service = await asyncio.to_thread(
                build_services_from_refresh_token,
                refresh,
                GOOGLE_OAUTH_CLIENT_ID,
                GOOGLE_OAUTH_CLIENT_SECRET,
            )
            with tempfile.TemporaryDirectory() as tmp:
                png = await asyncio.to_thread(
                    make_gslides_preview,
                    file_id,
                    job.get("source_lang", "auto"),
                    job.get("target_lang", "ja"),
                    tmp,
                    slides_service,
                    drive_service,
                )
                await _upload_preview_png(client, job["user_id"], job_id, png)
            return

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "input.pptx")
            await _storage_download(client, job["input_storage_path"], src)
            png = await asyncio.to_thread(
                make_preview,
                src,
                job.get("source_lang", "en"),
                job.get("target_lang", "ja"),
                tmp,
            )
            await _upload_preview_png(client, job["user_id"], job_id, png)


@app.post("/preview", status_code=202)
async def preview(req: RunRequest, authorization: str = Header(default="")):
    if not SHARED_SECRET or authorization != f"Bearer {SHARED_SECRET}":
        raise HTTPException(status_code=401, detail="unauthorized")
    asyncio.create_task(_preview(req.job_id))
    return {"accepted": req.job_id}


@app.get("/health")
async def health():
    return {"ok": True, "concurrency": WORKER_CONCURRENCY}
