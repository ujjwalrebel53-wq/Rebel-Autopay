#!/usr/bin/env python3
"""Generate encrypted vault.bin and encrypted_config.h for Rebel Autopay."""

import os
import struct
import secrets

VAULT_PLAIN_SIZE = 6_500_000
KEY_LEN = 32
P1 = bytes([0x52, 0x65, 0x62, 0x65, 0x6C, 0x41, 0x75, 0x74, 0x6F, 0x70, 0x61, 0x79, 0x56, 0x31, 0x2E, 0x30])
P2 = bytes([0x9F, 0x3A, 0xC1, 0x77, 0x2E, 0x88, 0x41, 0xD3, 0x6C, 0x19, 0xFA, 0x05, 0xB2, 0x67, 0xDC, 0x31])

TELEGRAM_LINK = b"https://t.me/+wEODy3Qd2xRhZTI1"


def derive_key():
    key = bytearray(KEY_LEN)
    for i in range(KEY_LEN):
        key[i] = P1[i % 16] ^ P2[i % 16] ^ ((i * 7 + 13) & 0xFF)
    return bytes(key)


def xor_crypt(data: bytes, key: bytes) -> bytes:
    out = bytearray(len(data))
    for i, b in enumerate(data):
        out[i] = b ^ key[i % len(key)]
    return bytes(out)


def encrypt_string(value: bytes, key: bytes) -> bytes:
    return xor_crypt(value, key)


def build_plain_vault(logo_path: str) -> bytes:
    with open(logo_path, "rb") as f:
        logo = f.read()

    payload = bytearray()
    payload += b"RBL1"
    payload += struct.pack("<I", len(logo))
    payload += logo
    payload += struct.pack("<I", len(TELEGRAM_LINK))
    payload += TELEGRAM_LINK
    payload += secrets.token_bytes(max(0, VAULT_PLAIN_SIZE - len(payload)))
    if len(payload) != VAULT_PLAIN_SIZE:
        raise RuntimeError(f"Vault size mismatch: {len(payload)} != {VAULT_PLAIN_SIZE}")
    return bytes(payload)


def write_encrypted_header(strings, key: bytes):
  lines = [
      "#pragma once",
      "#include <cstddef>",
      "",
      f"static const unsigned char VAULT_KEY[{KEY_LEN}] = {{",
      ", ".join(f"0x{b:02X}" for b in key),
      "};",
      "",
      f"static const size_t VAULT_KEY_LEN = {KEY_LEN};",
      "",
  ]
  for name, value in strings:
      enc = encrypt_string(value, key)
      lines.append(f"static const unsigned char {name}[] = {{")
      lines.append(", ".join(f"0x{b:02X}" for b in enc) + "};")
      lines.append(f"static const size_t {name}_LEN = {len(enc)};")
      lines.append("")
  path = os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "cpp", "encrypted_config.h")
  with open(path, "w", encoding="utf-8") as f:
      f.write("\n".join(lines))


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    logo_path = os.path.join(root, "app", "vault", "logo.png")
    vault_out = os.path.join(root, "app", "src", "main", "assets", "sec", "vault.bin")

    if not os.path.exists(logo_path):
        raise FileNotFoundError(f"Logo not found: {logo_path}")

    key = derive_key()
    plain = build_plain_vault(logo_path)
    encrypted = xor_crypt(plain, key)

    os.makedirs(os.path.dirname(vault_out), exist_ok=True)
    with open(vault_out, "wb") as f:
        f.write(encrypted)

    write_encrypted_header([
        ("ENC_COMMUNITY_LINK", TELEGRAM_LINK),
        ("ENC_OWNER_LINK", TELEGRAM_LINK),
    ], key)

    print(f"Generated vault: {vault_out} ({len(encrypted)} bytes)")
    print(f"Generated encrypted_config.h")


if __name__ == "__main__":
    main()
