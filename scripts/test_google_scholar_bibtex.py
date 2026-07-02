import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gbt7714_cite import parse_markdown_entries


DEFAULT_QUERIES = [
    "Inverse lithography technology ILT what is the impact to the photomask industry",
    "Trade-off between inverse lithography mask complexity and lithographic performance",
    "Inverse lithography technology ILT a natural solution for model-based SRAF at 45nm and 32nm",
    "Pushing the lithography limit applying inverse lithography technology ILT at the 65nm generation",
]
PAGE_RE = re.compile(r"\bpages?\s*=\s*[{'\"]([^}'\"]+)", re.IGNORECASE)


def import_scholarly():
    try:
        from scholarly import scholarly
    except ImportError as exc:
        raise SystemExit(
            "缺少 scholarly。请先运行：python -m pip install scholarly"
        ) from exc
    return scholarly


def compact(value: Any) -> str:
    text = str(value or "")
    return re.sub(r"\s+", " ", text).strip()


def extract_bibtex_pages(bibtex: str) -> str:
    match = PAGE_RE.search(bibtex or "")
    return match.group(1).replace("--", "-").strip() if match else ""


def load_queries(args: argparse.Namespace) -> list[str]:
    if args.query:
        return args.query

    if args.input:
        text = args.input.read_text(encoding="utf-8")
        entries = parse_markdown_entries(text)
        queries = []
        for entry in entries[: args.limit]:
            queries.append(entry.doi or entry.title)
        return queries

    return DEFAULT_QUERIES[: args.limit]


def fetch_one(scholarly, query: str, max_results: int) -> list[dict[str, Any]]:
    rows = []
    search = scholarly.search_pubs(query)
    for rank in range(1, max_results + 1):
        try:
            pub = next(search)
        except StopIteration:
            break

        bib = pub.get("bib", {})
        row = {
            "query": query,
            "rank": rank,
            "title": compact(bib.get("title")),
            "authors": compact(bib.get("author")),
            "year": compact(bib.get("pub_year")),
            "venue": compact(bib.get("venue")),
            "url": compact(pub.get("pub_url") or pub.get("eprint_url") or pub.get("link")),
            "bibtex": "",
            "bibtex_pages": "",
            "error": "",
        }

        try:
            bibtex = scholarly.bibtex(pub)
            row["bibtex"] = bibtex
            row["bibtex_pages"] = extract_bibtex_pages(bibtex)
        except Exception as exc:
            row["error"] = f"bibtex: {type(exc).__name__}: {exc}"

        rows.append(row)
    if not rows:
        rows.append(
            {
                "query": query,
                "rank": "",
                "title": "",
                "authors": "",
                "year": "",
                "venue": "",
                "url": "",
                "bibtex": "",
                "bibtex_pages": "",
                "error": "no_results",
            }
        )
    return rows


def write_outputs(rows: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = output.with_suffix(".csv")
    fieldnames = [
        "query",
        "rank",
        "title",
        "authors",
        "year",
        "venue",
        "url",
        "bibtex_pages",
        "error",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="用 Google Scholar/scholarly 试验 DOI 或标题的 BibTeX 页码质量"
    )
    parser.add_argument("query", nargs="*", help="要搜索的 DOI 或标题")
    parser.add_argument(
        "--input",
        type=Path,
        help="从 LitReviewFlow Markdown 文献清单读取 DOI/标题",
    )
    parser.add_argument("--limit", type=int, default=4, help="读取/测试的查询数量")
    parser.add_argument(
        "--max-results",
        type=int,
        default=1,
        help="每个查询保留的 Scholar 结果数量",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=5.0,
        help="每个查询之间的等待秒数，降低被限流概率",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scholar_bibtex_test.json"),
        help="JSON 输出路径；同时生成同名 CSV",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    scholarly = import_scholarly()
    queries = load_queries(args)

    rows = []
    for index, query in enumerate(queries, 1):
        print(f"[{index}/{len(queries)}] 搜索：{query}")
        try:
            rows.extend(fetch_one(scholarly, query, args.max_results))
        except Exception as exc:
            rows.append(
                {
                    "query": query,
                    "rank": "",
                    "title": "",
                    "authors": "",
                    "year": "",
                    "venue": "",
                    "url": "",
                    "bibtex": "",
                    "bibtex_pages": "",
                    "error": f"search: {type(exc).__name__}: {exc}",
                }
            )
        if index < len(queries):
            time.sleep(args.sleep)

    write_outputs(rows, args.output)
    print(f"已生成：{args.output}")
    print(f"已生成：{args.output.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
