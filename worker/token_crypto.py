"""
AES-256-GCM decrypt for the customer's Google OAuth refresh token (gslides path).

The decryption counterpart to decktr-web's lib/crypto.ts. The Next.js app encrypts the
refresh token on /api/google/exchange and stores the ciphertext on the job row; this
worker decrypts it to mint a fresh access token at fulfillment time. The two sides MUST
agree on this wire format byte-for-byte:

    v1:<base64(iv)>:<base64(ciphertext)>:<base64(tag)>

iv = 12 bytes, tag = 16-byte GCM auth tag. Key = base64-decoded GOOGLE_TOKEN_ENC_KEY
(32 bytes). The SAME key must be set on Vercel (server) and this worker's env.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _key() -> bytes:
    raw = os.environ.get("GOOGLE_TOKEN_ENC_KEY", "")
    if not raw:
        raise RuntimeError("GOOGLE_TOKEN_ENC_KEY is not set")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError(
            f"GOOGLE_TOKEN_ENC_KEY must decode to 32 bytes (got {len(key)})"
        )
    return key


def decrypt_token(blob: str) -> str:
    """Reverse lib/crypto.ts::encryptToken. Raises on tamper / wrong key / bad format."""
    try:
        version, iv_b64, ct_b64, tag_b64 = blob.split(":")
    except ValueError as exc:
        raise ValueError("malformed encrypted token") from exc
    if version != "v1":
        raise ValueError(f"unsupported token envelope version: {version}")
    iv = base64.b64decode(iv_b64)
    ct = base64.b64decode(ct_b64)
    tag = base64.b64decode(tag_b64)
    # AESGCM expects ciphertext||tag; Node exposes the tag separately, so re-join here.
    plaintext = AESGCM(_key()).decrypt(iv, ct + tag, None)
    return plaintext.decode("utf-8")
