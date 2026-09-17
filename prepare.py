#!/usr/bin/env python3
"""Create private local configuration without overwriting existing credentials."""
import os
from pathlib import Path
import secrets


def prepare(root):
    root = Path(root)
    (root / "runtime/files").mkdir(parents=True, exist_ok=True)
    (root / "runtime/models/bge-reranker-base").mkdir(parents=True, exist_ok=True)
    env_file = root / ".env"
    try:
        descriptor = os.open(str(env_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("Existing .env preserved.")
    else:
        with os.fdopen(descriptor, "w") as stream:
            stream.write("DB_PASSWORD=" + secrets.token_hex(24) + "\n")
            stream.write("JWT_SECRET_KEY=" + secrets.token_hex(32) + "\n")
        print("Created .env with unique local credentials.")
    print("Runtime directories ready.")


if __name__ == "__main__":
    prepare(Path(__file__).resolve().parent)
