import hashlib
import hmac
import os
from functools import lru_cache

from ecdsa import BadSignatureError, SECP256k1, SigningKey

SECRET_ENV_NAME = "BLOCKCHAIN_SECRET_KEY"
DEFAULT_SECRET = "dev-secret-change-me"


def _get_secret() -> bytes:
    secret = os.getenv(SECRET_ENV_NAME, DEFAULT_SECRET)
    return secret.encode("utf-8")


def get_secret_fingerprint() -> str:
    # Short fingerprint to detect secret-key changes across sessions.
    return hashlib.sha256(_get_secret()).hexdigest()[:16]


@lru_cache(maxsize=1)
def _get_signing_key() -> SigningKey:
    # Deterministically derive a valid secret exponent from the configured secret.
    seed_int = int.from_bytes(hashlib.sha256(_get_secret() + b"|ecdsa").digest(), "big")
    order = SECP256k1.order
    secret_exponent = (seed_int % (order - 1)) + 1
    return SigningKey.from_secret_exponent(secret_exponent, curve=SECP256k1)


@lru_cache(maxsize=1)
def _get_verifying_key():
    return _get_signing_key().get_verifying_key()


def generate_security_id(block_index: int, data_hash: str, prev_hash: str) -> str:
    payload = f"{block_index}|{data_hash}|{prev_hash}".encode("utf-8")
    digest = hmac.new(_get_secret(), payload, hashlib.sha256).hexdigest()
    return f"SID-{digest[:24]}"


def sign_block_payload(payload: str) -> str:
    signing_key = _get_signing_key()
    signature = signing_key.sign_deterministic(
        payload.encode("utf-8"), hashfunc=hashlib.sha256
    )
    return signature.hex()


def verify_block_signature(payload: str, signature_hex: str) -> bool:
    verifying_key = _get_verifying_key()
    try:
        if verifying_key is None:
            return False

        return verifying_key.verify(
            bytes.fromhex(signature_hex),
            payload.encode("utf-8"),
            hashfunc=hashlib.sha256,
        )
    except (BadSignatureError, ValueError):
        return False
