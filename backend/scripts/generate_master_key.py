#!/usr/bin/env python3
"""Generate a Fernet master key for NVISION_MASTER_KEY.

Usage:
    python backend/scripts/generate_master_key.py
"""
from cryptography.fernet import Fernet

if __name__ == "__main__":
    print(Fernet.generate_key().decode())
