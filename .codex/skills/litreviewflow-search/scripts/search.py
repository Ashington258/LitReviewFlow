from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_MARKERS = (Path("scripts/search_literature.py"), Path("litreviewflow"))


def _is_project_root(path: Path) -> bool:
    return all((path / marker).exists() for marker in PROJECT_MARKERS)


def _candidate_roots(start: Path):
    yield start
    yield from start.parents


def find_project_root(explicit: str | None = None) -> Path:
    configured = [explicit, os.getenv("LITREVIEWFLOW_HOME")]
    for value in configured:
        if not value:
            continue
        candidate = Path(value).expanduser().resolve()
        if _is_project_root(candidate):
            return candidate
        raise FileNotFoundError(f"LitReviewFlow project not found at configured path: {candidate}")

    starts = (Path.cwd().resolve(), Path(__file__).resolve())
    seen: set[Path] = set()
    for start in starts:
        for candidate in _candidate_roots(start):
            if candidate in seen:
                continue
            seen.add(candidate)
            if _is_project_root(candidate):
                return candidate

    raise FileNotFoundError(
        "Could not locate LitReviewFlow. Run from the repository, set "
        "LITREVIEWFLOW_HOME, or pass --project-root."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LitReviewFlow literature search.")
    parser.add_argument("query")
    parser.add_argument("--project-root", help="Path to a LitReviewFlow checkout.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--year-from", type=int, default=2024)
    parser.add_argument("--year-to", type=int, default=2026)
    parser.add_argument("--providers", default="openalex,semantic_scholar")
    parser.add_argument("--sort", choices=["relevance", "citation_count", "year"], default="relevance")
    parser.add_argument("--no-semantic-search", action="store_true")
    args = parser.parse_args()

    project = find_project_root(args.project_root)
    script = project / "scripts" / "search_literature.py"

    command = [
        sys.executable,
        str(script),
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

    completed = subprocess.run(command, cwd=project)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
