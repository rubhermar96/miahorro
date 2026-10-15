import secrets

from app.security.encryption import keyed_hash

CODE_COUNT = 10
# No 0/o, 1/l/i: codes are read off paper and typed by hand.
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def new_codes() -> list[str]:
    def code() -> str:
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(10))
        return f"{raw[:5]}-{raw[5:]}"

    return [code() for _ in range(CODE_COUNT)]


def normalise(code: str) -> str:
    return code.lower().replace("-", "").replace(" ", "").strip()


def hash_code(secret_key: str, code: str) -> str:
    return keyed_hash(secret_key, normalise(code))
