"""Generate the VAPID key pair that identifies your server to browsers' push services. Run ONCE:

    python scripts/gen_vapid.py

Put the two printed values in Render -> Environment. Keep the PRIVATE key secret (never commit it)."""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


key = ec.generate_private_key(ec.SECP256R1())
private_raw = key.private_numbers().private_value.to_bytes(32, "big")
public_raw = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)

print("VAPID_PUBLIC_KEY=" + b64(public_raw))
print("VAPID_PRIVATE_KEY=" + b64(private_raw))
