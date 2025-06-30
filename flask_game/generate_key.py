#!/usr/bin/env python3
"""
Utility script to generate a secure Flask SECRET_KEY
"""
import secrets

def generate_secret_key():
    """Generate a cryptographically secure secret key"""
    return secrets.token_hex(32)  # 32 bytes = 64 hex characters

if __name__ == "__main__":
    key = generate_secret_key()
    print("Generated SECRET_KEY:")
    print(key)
    print("\nCopy this key to your .env file:")
    print(f"SECRET_KEY={key}") 