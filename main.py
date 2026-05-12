import argparse
import sys

from sync import SyncEngine


def main() -> int:
    p = argparse.ArgumentParser(description="Sync Encircle property claims + media to CompanyCam")
    p.add_argument("--execute", action="store_true", help="Actually create projects + upload photos. Without this, runs in dry-run mode.")
    sub = p.add_subparsers(dest="cmd", required=True)

    one = sub.add_parser("claim", help="Sync a single Encircle property claim")
    one.add_argument("claim_id", help="Encircle property_claim_id (e.g. 4580042)")

    recent = sub.add_parser("recent", help="Sync N most recent Encircle property claims")
    recent.add_argument("--max", type=int, default=10, help="Max claims to sync (default 10)")

    args = p.parse_args()

    engine = SyncEngine(dry_run=not args.execute)

    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"=== Encircle → CompanyCam sync ({mode}) ===")

    if args.cmd == "claim":
        engine.sync_claim(args.claim_id)
    elif args.cmd == "recent":
        engine.sync_recent(max_claims=args.max)

    return 0


if __name__ == "__main__":
    sys.exit(main())
