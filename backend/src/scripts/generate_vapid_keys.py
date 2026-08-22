"""Generates a VAPID key pair for Web Push and prints them ready to paste into .env.

Both keys are printed in "raw" base64url form (no PEM/DER) - VAPID_PUBLIC_KEY is exactly what the
browser's PushManager.subscribe({applicationServerKey}) expects, and VAPID_PRIVATE_KEY is a format
py_vapid.Vapid.from_string (which pywebpush calls internally) recognizes on its own by length, no
extra config needed on either side.

Run with `uv run python -m scripts.generate_vapid_keys` from backend/. Does not touch .env itself
(mirrors scripts/bootstrap_db_role.py's own DB_APP_PASSWORD - a secret this script only ever
prints, never writes) and does not read config.py/Settings, so it needs no other env vars set.
"""

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02
from py_vapid.utils import b64urlencode


def main() -> None:
    vapid = Vapid02()
    vapid.generate_keys()

    private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )

    print("Paste into .env:")
    print(f"VAPID_PUBLIC_KEY={b64urlencode(public_raw)}")
    print(f"VAPID_PRIVATE_KEY={b64urlencode(private_raw)}")
    print("VAPID_CONTACT_EMAIL=<your own email - sent to the push service with every push>")


if __name__ == "__main__":
    main()
