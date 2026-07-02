from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from litreviewflow.models import SearchRequest
from litreviewflow.service import LiteratureService
from litreviewflow.config import load_settings


def _parse_providers(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_dois(values: list[str] | None, doi_file: str | None) -> list[str]:
    dois: list[str] = []
    for value in values or []:
        dois.extend(item.strip() for item in value.split(",") if item.strip())
    if doi_file:
        for line in Path(doi_file).read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                dois.append(stripped)
    return dois


def _dump_response(result, output_mode: str) -> str:
    data = result.model_dump()
    if output_mode in {"english", "bilingual"}:
        for paper in data["papers"]:
            paper["abstract_en_raw"] = paper.get("abstract_en_raw") or paper.get("abstract")
    if output_mode == "bilingual":
        for paper in data["papers"]:
            paper.setdefault("abstract_zh", None)
    return json.dumps(data, ensure_ascii=False, indent=2)


def main() -> None:
    settings = load_settings()
    defaults = settings.search_defaults
    parser = argparse.ArgumentParser(description="Search literature and print normalized JSON.")
    parser.add_argument("query", nargs="?", default=defaults.query, help="Keyword string or research direction.")
    parser.add_argument("--limit", type=int, default=defaults.limit)
    parser.add_argument("--providers", default=",".join(defaults.providers), help="Comma-separated provider list.")
    parser.add_argument("--year-from", type=int, default=defaults.year_from)
    parser.add_argument("--year-to", type=int, default=defaults.year_to)
    parser.add_argument("--sort", choices=["relevance", "citation_count", "year"], default=defaults.sort)
    parser.add_argument("--semantic-search", action="store_true", default=defaults.semantic_search)
    parser.add_argument("--no-semantic-search", action="store_false", dest="semantic_search")
    parser.add_argument("--require-abstract", action="store_true", default=defaults.require_abstract)
    parser.add_argument("--allow-missing-abstract", action="store_false", dest="require_abstract")
    parser.add_argument("--include-raw", action="store_true", default=defaults.include_raw)
    parser.add_argument("--doi", action="append", help="Exact DOI lookup. Can be repeated or comma-separated.")
    parser.add_argument("--doi-file", help="UTF-8 text file with one DOI per line.")
    parser.add_argument("--exact-doi", action="store_true", help="Treat query as an exact DOI instead of keyword search.")
    parser.add_argument(
        "--output",
        choices=["default", "english", "bilingual"],
        default="default",
        help="Add explicit abstract_en_raw and optional abstract_zh fields to JSON output.",
    )
    args = parser.parse_args()
    dois = _parse_dois(args.doi, args.doi_file)
    if not args.query and not dois:
        parser.error("query is required when config.search_defaults.query is empty.")

    service = LiteratureService()
    result = service.search(
        SearchRequest(
            query=args.query or "DOI lookup",
            limit=args.limit,
            providers=_parse_providers(args.providers),
            dois=dois,
            exact_doi=args.exact_doi,
            year_from=args.year_from,
            year_to=args.year_to,
            sort=args.sort,
            require_abstract=args.require_abstract,
            semantic_search=args.semantic_search,
            include_raw=args.include_raw,
        )
    )
    print(_dump_response(result, args.output))


if __name__ == "__main__":
    main()
