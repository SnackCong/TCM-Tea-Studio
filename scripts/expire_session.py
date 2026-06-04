#!/usr/bin/env python3
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Expire one existing login session for verification.")
    parser.add_argument("--token", required=True, help="Session token from a controlled test cookie jar.")
    parser.add_argument("--confirm", required=True, help="Must be exactly EXPIRE_SESSION.")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.confirm != "EXPIRE_SESSION":
        print("refusing: pass --confirm EXPIRE_SESSION", file=sys.stderr)
        return 2

    server.init_db()
    with server.connect() as conn:
        result = conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE token = ?",
            (int(time.time()) - 1, args.token),
        )
        print(f"expired_sessions={result.rowcount}")
    return 0 if result.rowcount == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
