#!/usr/bin/env python3
"""
One-time keypair generation for AIControl license signing.
Run once: python scripts/generate_keypair.py
Save private key to your password manager.
Paste public key into app/core/license.py PUBLIC_KEY constant.
"""
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
)

public_pem = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)

print("=" * 60)
print("PRIVATE KEY — save to password manager, never commit")
print("=" * 60)
print(private_pem.decode())
print("=" * 60)
print("PUBLIC KEY — paste into app/core/license.py PUBLIC_KEY")
print("=" * 60)
print(public_pem.decode())
