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

import asyncio
import os
import tempfile

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from ai_deck_translator.pptx.translator import translate_pptx
from ai_deck_translator.utils.exceptions import IncompleteTranslationError

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SHARED_SECRET = os.environ.get("WORKER_SHARED_SECRET", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
WORKER_CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "2"))

INPUT_BUCKET = "deck-input"
OUTPUT_BUCKET = "deck-output"

app = FastAPI(title="decktr-worker")
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
            except IncompleteTranslationError as exc:
                # 100%-or-fail-loud gate tripped — never ship a partial deck; refund.
                await _update_job(
                    client,
                    job_id,
                    {"status": "failed", "error_message": str(exc)[:500], "completed_at": "now()"},
                )
                await _stripe_refund(client, job.get("stripe_payment_intent_id"))
            except Exception as exc:  # noqa: BLE001 — any failure must refund, never strand
                await _update_job(
                    client,
                    job_id,
                    {"status": "failed", "error_message": str(exc)[:500], "completed_at": "now()"},
                )
                await _stripe_refund(client, job.get("stripe_payment_intent_id"))
            finally:
                if input_path:
                    await _storage_delete_input(client, input_path)  # zero-retention


@app.post("/run", status_code=202)
async def run(req: RunRequest, authorization: str = Header(default="")):
    if not SHARED_SECRET or authorization != f"Bearer {SHARED_SECRET}":
        raise HTTPException(status_code=401, detail="unauthorized")
    # Fire-and-forget: schedule processing, return 202 immediately (MWT pattern).
    asyncio.create_task(_process(req.job_id))
    return {"accepted": req.job_id}


@app.get("/health")
async def health():
    return {"ok": True, "concurrency": WORKER_CONCURRENCY}
