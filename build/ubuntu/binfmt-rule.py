#!/usr/bin/env python3
"""Emit an architecture-specific textual binfmt rule; never register it here."""
import sys
from pathlib import Path

MAGIC = bytes.fromhex('7f454c460201010000000000000000000200b700')
MASK = bytes.fromhex('ffffffffffffff00fffffffffffffffffeffffff')


def matches(header):
    return len(header) >= len(MAGIC) and all(
        (actual & mask) == (magic & mask)
        for actual, magic, mask in zip(header, MAGIC, MASK)
    )


def rule(interpreter):
    if matches(Path(interpreter).read_bytes()[:20]):
        raise ValueError('Refusing a rule that matches its own interpreter')
    if matches(Path('/bin/sh').read_bytes()[:20]):
        raise ValueError('Refusing a rule that matches the native shell')
    escape = lambda data: ''.join(f'\\x{byte:02x}' for byte in data)
    return f':blikvm-m7-aarch64:M::{escape(MAGIC)}:{escape(MASK)}:{interpreter}:F'


if __name__ == '__main__':
    print(rule(sys.argv[1]))
