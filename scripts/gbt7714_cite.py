import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


DOI_RE = re.compile(r"10\.\d{4,9}/[^\s，。；;,）)]+", re.IGNORECASE)
ENTRY_RE = re.compile(
    r"^###\s+(?P<number>\d+)\.\s+(?P<title>.+?)\s*$"
    r"(?P<body>.*?)(?=^###\s+\d+\.|\Z)",
    re.MULTILINE | re.DOTALL,
)
DEFAULT_OVERRIDES_PATH = Path("config/gbt7714_overrides.json")
SPIE_CID_RE = re.compile(r"^\d{4,5}[0-9A-Z]{1,2}$", re.IGNORECASE)


@dataclass
class MarkdownEntry:
    number: int
    title: str
    doi: str | None
    authors: list[str]
    year: str | None


def fetch_by_doi(doi: str) -> dict[str, Any] | None:
    url = f"https://api.crossref.org/works/{doi}"
    headers = {"Accept": "application/json"}
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code == 200:
        return resp.json().get("message")
    return None


def normalize_doi(doi: str) -> str:
    return doi.strip().rstrip(".").lower()


def load_overrides(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    return {normalize_doi(doi): fields for doi, fields in data.items()}


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def apply_field_corrections(
    item: dict[str, Any], overrides: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    doi = item.get("DOI")
    if not doi:
        return item

    corrections = (overrides or {}).get(normalize_doi(doi))
    if not corrections:
        return item

    return deep_merge(item, corrections)


def has_override_field(
    item: dict[str, Any], overrides: dict[str, dict[str, Any]] | None, field: str
) -> bool:
    doi = item.get("DOI")
    return bool(doi and field in (overrides or {}).get(normalize_doi(doi), {}))


def search_by_title(title: str) -> dict[str, Any] | None:
    url = (
        "https://api.crossref.org/works"
        f"?query.bibliographic={quote(title)}&sort=relevance&order=desc&rows=1"
    )
    headers = {"Accept": "application/json"}
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code == 200:
        items = resp.json().get("message", {}).get("items", [])
        return items[0] if items else None
    return None


def clean_text(value: Any) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    text = str(value or "")
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .")


def clean_container_name(value: Any, prefer_last: bool = False) -> str:
    values = value if isinstance(value, list) else [value]
    names = [clean_text(item) for item in values if clean_text(item)]
    if not names:
        return ""
    if prefer_last:
        for name in reversed(names):
            if name.lower() not in {"spie proceedings", "proceedings"}:
                return name
    return names[0].replace(", and ", " and ")


def sentence_case_title(title: str) -> str:
    title = clean_text(title)
    if not title:
        return title
    return title[0].upper() + title[1:]


def initials(given: str) -> str:
    parts = re.findall(r"[A-Za-z]+", given.replace("-", " "))
    return " ".join(part[0].upper() for part in parts)


def format_author_name(author: dict[str, Any] | str) -> str:
    if isinstance(author, str):
        return author.strip()

    given = clean_text(author.get("given"))
    family = clean_text(author.get("family"))
    if family and given:
        suffix = initials(given)
        return f"{family} {suffix}".strip()
    return family or given or "未知作者"


def format_authors(authors: list[dict[str, Any]] | list[str], et_al: str = "et al.") -> str:
    if not authors:
        return "未知作者"

    if len(authors) > 3:
        visible = authors[:3]
        suffix = et_al
    else:
        visible = authors
        suffix = ""

    names = [format_author_name(author) for author in visible]
    if suffix:
        names.append(suffix)
    return ", ".join(names)


def join_author_title(authors: str, title: str, doc_type: str) -> str:
    separator = " " if authors.endswith(".") else ". "
    return f"{authors}{separator}{title}[{doc_type}]"


def fallback_authors(author_line: str | None) -> list[str]:
    if not author_line:
        return []
    names = [name.strip() for name in author_line.split(",") if name.strip()]
    return names


def get_year(item: dict[str, Any], fallback: str | None = None) -> str:
    for key in ("published-print", "published-online", "issued"):
        parts = item.get(key, {}).get("date-parts", [])
        if parts and parts[0] and parts[0][0]:
            return str(parts[0][0])
    return fallback or "未知年份"


def get_doc_type(item: dict[str, Any]) -> str:
    item_type = item.get("type", "journal-article")
    if item_type in {"journal-article", "journal"}:
        return "J"
    if item_type in {"proceedings-article", "proceedings", "conference-paper"}:
        return "C"
    if "book" in item_type:
        return "M"
    if "dissertation" in item_type or "thesis" in item_type:
        return "D"
    return "J"


def is_spie_proceedings(item: dict[str, Any]) -> bool:
    publisher = clean_text(item.get("publisher")).lower()
    containers = item.get("container-title") or []
    if not isinstance(containers, list):
        containers = [containers]
    names = " ".join(clean_text(name).lower() for name in containers)
    return "spie" in publisher or "spie proceedings" in names


def looks_like_spie_cid(page: str, volume: str) -> bool:
    normalized = page.strip()
    if not normalized or "-" in normalized:
        return False
    if volume and normalized.startswith(volume) and SPIE_CID_RE.match(normalized):
        return True
    return bool(SPIE_CID_RE.match(normalized) and re.search(r"[A-Z]$", normalized, re.IGNORECASE))


def join_volume_issue_pages(volume: str, issue: str, pages: str) -> str:
    parts = []
    if volume:
        parts.append(volume + (f"({issue})" if issue else ""))
    elif issue:
        parts.append(f"({issue})")
    if pages:
        if parts:
            parts[-1] = f"{parts[-1]}: {pages}"
        else:
            parts.append(pages)
    return ", ".join(parts)


def format_journal_article(
    authors: str, title: str, item: dict[str, Any], year: str
) -> str:
    journal = clean_container_name(item.get("container-title"))
    volume = clean_text(item.get("volume"))
    issue = clean_text(item.get("issue"))
    pages = clean_text(item.get("page"))
    tail = join_volume_issue_pages(volume, issue, pages)

    ref = f"{join_author_title(authors, title, 'J')}. {journal}, {year}"
    if tail:
        ref += f", {tail}"
    return ref + "."


def format_conference_article(
    authors: str,
    title: str,
    item: dict[str, Any],
    year: str,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> str:
    event = clean_text(item.get("event", {}).get("name"))
    container = clean_container_name(item.get("container-title"), prefer_last=True)
    conference = container or event
    publisher = clean_text(item.get("publisher"))
    volume = clean_text(item.get("volume"))
    pages = clean_text(item.get("page"))
    if (
        is_spie_proceedings(item)
        and looks_like_spie_cid(pages, volume)
        and not has_override_field(item, overrides, "page")
    ):
        pages = ""

    ref = join_author_title(authors, title, "C")
    if conference:
        ref += f"//{conference}. "
    else:
        ref += ". "
    if publisher:
        ref += f"{publisher}, "
    ref += year
    if volume:
        ref += f", {volume}"
    if pages:
        ref += f": {pages}"
    return ref + "."


def format_generic(authors: str, title: str, doc_type: str, item: dict[str, Any], year: str) -> str:
    publisher = clean_text(item.get("publisher"))
    ref = f"{join_author_title(authors, title, doc_type)}."
    if publisher:
        ref += f" {publisher}, {year}."
    else:
        ref += f" {year}."
    return ref


def format_gbt7714(
    item: dict[str, Any] | None,
    fallback_title: str | None = None,
    fallback_authors_value: list[str] | None = None,
    fallback_year: str | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> str:
    if not item:
        authors = format_authors(fallback_authors_value or [])
        title = sentence_case_title(fallback_title or "")
        year = fallback_year or "未知年份"
        return f"{authors}. {title}[J]. {year}."

    item = apply_field_corrections(item, overrides)
    authors = format_authors(item.get("author") or fallback_authors_value or [])
    title = sentence_case_title(item.get("title") or fallback_title or "")
    doc_type = get_doc_type(item)
    year = get_year(item, fallback_year)

    if doc_type == "J":
        return format_journal_article(authors, title, item, year)
    if doc_type == "C":
        return format_conference_article(authors, title, item, year, overrides)
    return format_generic(authors, title, doc_type, item, year)


def extract_field(body: str, field: str) -> str | None:
    match = re.search(rf"^- {re.escape(field)}：(.+?)\s*$", body, re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_markdown_entries(text: str) -> list[MarkdownEntry]:
    entries = []
    for match in ENTRY_RE.finditer(text):
        body = match.group("body")
        doi_line = extract_field(body, "DOI")
        doi_match = DOI_RE.search(doi_line or "")
        authors = fallback_authors(extract_field(body, "作者"))
        entries.append(
            MarkdownEntry(
                number=int(match.group("number")),
                title=match.group("title").strip(),
                doi=doi_match.group(0) if doi_match else None,
                authors=authors,
                year=extract_field(body, "年份"),
            )
        )
    return entries


def cite_entry(entry: MarkdownEntry, overrides: dict[str, dict[str, Any]]) -> str:
    item = fetch_by_doi(entry.doi) if entry.doi else search_by_title(entry.title)
    if item is None:
        item = search_by_title(entry.title)
    return format_gbt7714(item, entry.title, entry.authors, entry.year, overrides)


def cite_markdown(input_path: Path, output_path: Path, overrides_path: Path | None) -> None:
    text = input_path.read_text(encoding="utf-8")
    entries = parse_markdown_entries(text)
    if not entries:
        raise ValueError(f"未在 {input_path} 中识别到 Markdown 文献条目")

    overrides = load_overrides(overrides_path)
    lines = ["# 参考文献（GB/T 7714-2015）", ""]
    for entry in entries:
        try:
            citation = cite_entry(entry, overrides)
        except requests.RequestException as exc:
            citation = format_gbt7714(None, entry.title, entry.authors, entry.year)
            print(
                f"[WARN] {entry.number}. {entry.title}: Crossref 查询失败，使用本地元数据回退。{exc}",
                file=sys.stderr,
            )
        lines.append(f"{entry.number}. {citation}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 GB/T 7714-2015 参考文献格式")
    parser.add_argument("query", nargs="?", help="单条 DOI 或标题；未提供时进入交互模式")
    parser.add_argument("--input", "-i", type=Path, help="包含文献条目的 Markdown 文件")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="批量输出文件，默认在输入文件名后追加 _GB7714.md",
    )
    parser.add_argument(
        "--overrides",
        type=Path,
        default=DEFAULT_OVERRIDES_PATH,
        help="本地元数据校正 JSON 文件，默认 config/gbt7714_overrides.json",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.input:
        output = args.output or args.input.with_name(f"{args.input.stem}_GB7714.md")
        cite_markdown(args.input, output, args.overrides)
        print(f"已生成：{output}")
        return

    query = args.query
    if not query:
        print("GB/T 7714-2015 参考文献自动生成工具")
        print("输入文献 DOI（推荐）或标题：")
        query = input().strip()

    doi_match = DOI_RE.search(query)
    data = fetch_by_doi(doi_match.group(0)) if doi_match else search_by_title(query)
    overrides = load_overrides(args.overrides)
    print(format_gbt7714(data, query, overrides=overrides))


if __name__ == "__main__":
    main()
