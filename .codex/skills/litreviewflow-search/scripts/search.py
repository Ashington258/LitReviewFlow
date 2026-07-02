from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT = Path(r"E:\14.TOOLs\LitReviewFlow")
SCRIPT = PROJECT / "scripts" / "search_literature.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LitReviewFlow literature search.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--year-from", type=int, default=2024)
    parser.add_argument("--year-to", type=int, default=2026)
    parser.add_argument("--providers", default="openalex,semantic_scholar")
    parser.add_argument("--sort", choices=["relevance", "citation_count", "year"], default="relevance")
    parser.add_argument("--no-semantic-search", action="store_true")
    args = parser.parse_args()

    command = [
        sys.executable,
        str(SCRIPT),
        args.query,
        "--limit",
        str(args.limit),
        "--year-from",
        str(args.year_from),
        "--year-to",
        str(args.year_to),
        "--providers",
        args.providers,
        "--sort",
        args.sort,
    ]
    if args.no_semantic_search:
        command.append("--no-semantic-search")
    else:
        command.append("--semantic-search")

    completed = subprocess.run(command, cwd=PROJECT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
