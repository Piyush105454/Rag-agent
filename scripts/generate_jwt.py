#!/usr/bin/env python3
"""
scripts/generate_jwt.py

CLI utility to mint a test JWT for the RAG Knowledge Assistant.
Generates a signed JWT using the HS256 algorithm matching the backend
JWT_SECRET configuration. Prints the raw token and decoded payload for
easy verification during local development.

Usage:
    python generate_jwt.py --user-id alice --groups engineering,product --secret my_secret
    python generate_jwt.py --user-id bob --groups sales --secret my_secret --expires 3600
"""

import argparse
import json
import sys
import time
import base64
import hmac
import hashlib


def b64url_encode(data: bytes) -> str:
    """URL-safe base64 encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    """URL-safe base64 decode with padding restoration."""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def create_jwt(user_id: str, groups: list[str], secret: str, expires_in: int = 86400) -> str:
    """
    Mint a signed HS256 JWT token.

    Args:
        user_id:    Subject claim (user UUID or username)
        groups:     List of access group strings
        secret:     HMAC secret matching JWT_SECRET in .env
        expires_in: Token lifetime in seconds (default 24h)

    Returns:
        Signed JWT string
    """
    now = int(time.time())

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "groups": groups,
        "iat": now,
        "exp": now + expires_in,
    }

    header_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode())

    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = b64url_encode(signature)

    return f"{signing_input}.{signature_b64}"


def decode_jwt_payload(token: str) -> dict:
    """Decode the payload of a JWT without verifying the signature."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    return json.loads(b64url_decode(parts[1]).decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mint a test JWT for the RAG Knowledge Assistant"
    )
    parser.add_argument(
        "--user-id",
        default="test-user",
        help="Subject claim (user ID). Default: test-user",
    )
    parser.add_argument(
        "--groups",
        default="general",
        help="Comma-separated access groups. Default: general",
    )
    parser.add_argument(
        "--secret",
        default="changeme_dev_secret",
        help="JWT secret (must match JWT_SECRET in .env). Default: changeme_dev_secret",
    )
    parser.add_argument(
        "--expires",
        type=int,
        default=86400,
        help="Token lifetime in seconds. Default: 86400 (24h)",
    )

    args = parser.parse_args()
    groups = [g.strip() for g in args.groups.split(",") if g.strip()]

    token = create_jwt(
        user_id=args.user_id,
        groups=groups,
        secret=args.secret,
        expires_in=args.expires,
    )

    payload = decode_jwt_payload(token)

    print("=" * 60)
    print("JWT TOKEN")
    print("=" * 60)
    print(token)
    print()
    print("=" * 60)
    print("DECODED PAYLOAD")
    print("=" * 60)
    print(json.dumps(payload, indent=2))
    print()

    exp_dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(payload["exp"]))
    print(f"Expires at: {exp_dt}")
    print()
    print("Usage in curl:")
    print(f'  curl -H "Authorization: Bearer {token[:40]}..." http://localhost:8000/query')
    print()
    print("Usage in browser:")
    print("  Paste the token into the JWT field in the top-right of the chat UI.")


if __name__ == "__main__":
    main()
