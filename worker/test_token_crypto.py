"""Token-crypto tests — the AES-256-GCM envelope shared with decktr-web's lib/crypto.ts."""

import base64
import os

os.environ.setdefault("GOOGLE_TOKEN_ENC_KEY", base64.b64encode(os.urandom(32)).decode())

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from worker.token_crypto import decrypt_token


def _encrypt_like_app(plaintext: str) -> str:
    """Mirror lib/crypto.ts::encryptToken so we can prove decrypt parses its output."""
    key = base64.b64decode(os.environ["GOOGLE_TOKEN_ENC_KEY"])
    iv = os.urandom(12)
    ct_and_tag = AESGCM(key).encrypt(iv, plaintext.encode(), None)
    ct, tag = ct_and_tag[:-16], ct_and_tag[-16:]
    return (
        "v1:"
        + base64.b64encode(iv).decode()
        + ":"
        + base64.b64encode(ct).decode()
        + ":"
        + base64.b64encode(tag).decode()
    )


def test_round_trip():
    secret = "1//0gRefresh.Token_ABC-📊"
    assert decrypt_token(_encrypt_like_app(secret)) == secret


def test_malformed_blob_raises():
    with pytest.raises(ValueError):
        decrypt_token("not-a-valid-envelope")


def test_unknown_version_raises():
    with pytest.raises(ValueError):
        decrypt_token("v2:aaa:bbb:ccc")


def test_tamper_fails_authentication():
    blob = _encrypt_like_app("secret")
    version, iv, ct, tag = blob.split(":")
    # Flip the ciphertext → GCM auth tag check must fail (not silently return garbage).
    bad_ct = base64.b64encode(b"\x00" * len(base64.b64decode(ct))).decode()
    with pytest.raises(Exception):
        decrypt_token(f"{version}:{iv}:{bad_ct}:{tag}")
