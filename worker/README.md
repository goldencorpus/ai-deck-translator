# Decktr worker (VPS)

FastAPI service that fulfills SaaS translation jobs by running the existing engine
(`ai_deck_translator`). Triggered fire-and-forget from `decktr-web`'s `/api/translate`.
See `docs/saas-build-plan-2026.md` §1, §4D.

## Why on the VPS (not Vercel / Edge Functions)
python-pptx can't run on Supabase Edge Functions (Deno) and a 49-slide deck (~3–5 min) exceeds
Vercel function limits. The VPS runs the Python engine unchanged.

## Run (dev)
```bash
cd ai-deck-translator        # the package root (so `ai_deck_translator` imports)
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r worker/requirements.txt
uvicorn worker.app:app --host 0.0.0.0 --port 8787
```

## Env (set on the VPS — never commit)
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — DB + Storage (service role)
- `WORKER_SHARED_SECRET` — bearer the Vercel route must present
- `STRIPE_SECRET_KEY` — auto-refund on gate-failure
- `CLAUDE_API_KEY` — engine COGS key
- `WORKER_CONCURRENCY` — bounded pool (default 2)

## Deploy (systemd) — see `decktr-worker.service`
Front with HTTPS (caddy/nginx) + the bearer secret; optionally IP-allowlist Vercel egress.

## Status
Step-1 skeleton: engine call is real; Supabase/Stripe REST helpers are implemented and get
wired + verified end-to-end in step 2 (happy-path E2E). Stale-job re-triggers are idempotent
(the atomic claim in `_claim_job` guarantees single execution).
