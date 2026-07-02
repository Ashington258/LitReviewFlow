from __future__ import annotations

import time
from html import unescape
from re import search, sub
from typing import Any
from urllib.parse import quote

import requests

from .config import Settings
from .models import Paper, SortMode


OPENALEX_WORKS_URL = "https://api.openalex.org/works"
SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper"


class ProviderError(RuntimeError):
    pass


class HttpClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    def get(self, url: str, params: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.settings.request_timeout_seconds,
                )
                if response.status_code == 429:
                    sleep_seconds = min(2**attempt, 8)
                    time.sleep(sleep_seconds)
                    continue
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                time.sleep(min(2**attempt, 8))
        raise ProviderError(f"Request failed for {url}: {last_error}") from last_error


def reconstruct_openalex_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    if not inverted_index:
        return None
    positions = [position for values in inverted_index.values() for position in values]
    if not positions:
        return None
    words = [""] * (max(positions) + 1)
    for word, word_positions in inverted_index.items():
        for position in word_positions:
            if 0 <= position < len(words):
                words[position] = word
    text = " ".join(word for word in words if word).strip()
    return text or None


def _clean_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip().lower()


def extract_doi(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = text.strip().replace("https://doi.org/", "").replace("http://doi.org/", "")
    match = search(r"10\.\d{4,9}/\S+", cleaned, flags=0)
    if not match:
        return None
    return match.group(0).strip().rstrip(".,;)]}").lower()


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = sub(r"<[^>]+>", "", text)
    cleaned = unescape(cleaned)
    cleaned = sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


class OpenAlexClient:
    def __init__(self, http: HttpClient, settings: Settings) -> None:
        self.http = http
        self.settings = settings

    def search(
        self,
        query: str,
        limit: int,
        year_from: int | None,
        year_to: int | None,
        sort: SortMode,
        require_abstract: bool,
        semantic_search: bool,
        include_raw: bool,
    ) -> list[Paper]:
        params: dict[str, Any] = {
            "per_page": min(limit, 100),
            "select": ",".join(
                [
                    "id",
                    "doi",
                    "display_name",
                    "title",
                    "abstract_inverted_index",
                    "authorships",
                    "publication_year",
                    "publication_date",
                    "cited_by_count",
                    "primary_location",
                    "best_oa_location",
                    "open_access",
                    "concepts",
                    "topics",
                    "type",
                    "ids",
                    "language",
                ]
            ),
        }
        if semantic_search:
            params["search.semantic"] = query
        else:
            params["search"] = query
        if self.settings.openalex_api_key:
            params["api_key"] = self.settings.openalex_api_key

        filters = ["type:article"]
        if require_abstract:
            filters.append("has_abstract:true")
        if year_from:
            filters.append(f"publication_year:>{year_from - 1}")
        if year_to:
            filters.append(f"publication_year:<{year_to + 1}")
        if filters:
            params["filter"] = ",".join(filters)

        if sort == "citation_count" and not semantic_search:
            params["sort"] = "cited_by_count:desc"
        elif sort == "year":
            params["sort"] = "publication_year:desc"

        data = self.http.get(OPENALEX_WORKS_URL, params=params)
        return [self._parse_work(item, include_raw) for item in data.get("results", [])][:limit]

    def lookup_doi(self, doi: str, include_raw: bool) -> Paper:
        clean_doi = extract_doi(doi) or _clean_doi(doi)
        if not clean_doi:
            raise ProviderError(f"Invalid DOI: {doi}")
        url = f"{OPENALEX_WORKS_URL}/https://doi.org/{quote(clean_doi, safe='')}"
        params: dict[str, Any] = {}
        if self.settings.openalex_api_key:
            params["api_key"] = self.settings.openalex_api_key
        return self._parse_work(self.http.get(url, params=params), include_raw)

    def _parse_work(self, item: dict[str, Any], include_raw: bool) -> Paper:
        abstract = _clean_text(reconstruct_openalex_abstract(item.get("abstract_inverted_index")))
        primary_location = item.get("primary_location") or {}
        best_oa_location = item.get("best_oa_location") or {}
        location = best_oa_location or primary_location
        source = (primary_location.get("source") or {}) if isinstance(primary_location, dict) else {}
        authors = [
            (authorship.get("author") or {}).get("display_name", "")
            for authorship in item.get("authorships", [])
            if (authorship.get("author") or {}).get("display_name")
        ]
        concepts = [
            concept.get("display_name", "")
            for concept in item.get("concepts", [])
            if concept.get("display_name")
        ]
        topics = [
            topic.get("display_name", "")
            for topic in item.get("topics", [])
            if topic.get("display_name")
        ]
        ids = item.get("ids") or {}
        open_access_pdf = None
        if isinstance(location, dict):
            open_access_pdf = location.get("pdf_url")
        return Paper(
            id=item.get("id") or ids.get("openalex") or "",
            title=item.get("title") or item.get("display_name") or "",
            abstract=abstract,
            abstract_en_raw=abstract,
            summary=abstract,
            authors=authors,
            year=item.get("publication_year"),
            venue=source.get("display_name"),
            doi=_clean_doi(item.get("doi") or ids.get("doi")),
            url=ids.get("openalex") or item.get("id"),
            source="openalex",
            source_ids={key: str(value) for key, value in ids.items() if value},
            citation_count=item.get("cited_by_count"),
            fields_of_study=topics,
            concepts=concepts,
            open_access_pdf=open_access_pdf,
            landing_page_url=location.get("landing_page_url") if isinstance(location, dict) else None,
            abstract_source="openalex.abstract_inverted_index" if abstract else None,
            has_full_abstract=bool(abstract),
            raw=item if include_raw else None,
        )


class SemanticScholarClient:
    def __init__(self, http: HttpClient, settings: Settings) -> None:
        self.http = http
        self.settings = settings

    def search(
        self,
        query: str,
        limit: int,
        year_from: int | None,
        year_to: int | None,
        sort: SortMode,
        require_abstract: bool,
        include_raw: bool,
    ) -> list[Paper]:
        params: dict[str, Any] = {
            "query": query,
            "limit": min(limit, 100),
            "fields": ",".join(
                [
                    "paperId",
                    "corpusId",
                    "externalIds",
                    "title",
                    "abstract",
                    "tldr",
                    "authors",
                    "year",
                    "venue",
                    "url",
                    "citationCount",
                    "fieldsOfStudy",
                    "publicationTypes",
                    "openAccessPdf",
                ]
            ),
        }
        if year_from or year_to:
            start = str(year_from) if year_from else ""
            end = str(year_to) if year_to else ""
            params["year"] = f"{start}-{end}"
        if sort == "citation_count":
            params["sort"] = "citationCount:desc"
        elif sort == "year":
            params["sort"] = "year:desc"

        headers = {}
        if self.settings.semantic_scholar_api_key:
            headers["x-api-key"] = self.settings.semantic_scholar_api_key

        data = self.http.get(SEMANTIC_SCHOLAR_SEARCH_URL, params=params, headers=headers)
        papers = [self._parse_paper(item, include_raw) for item in data.get("data", [])]
        if require_abstract:
            papers = [paper for paper in papers if paper.abstract]
        return papers[:limit]

    def lookup_doi(self, doi: str, include_raw: bool) -> Paper:
        clean_doi = extract_doi(doi) or _clean_doi(doi)
        if not clean_doi:
            raise ProviderError(f"Invalid DOI: {doi}")
        params: dict[str, Any] = {
            "fields": ",".join(
                [
                    "paperId",
                    "corpusId",
                    "externalIds",
                    "title",
                    "abstract",
                    "tldr",
                    "authors",
                    "year",
                    "venue",
                    "url",
                    "citationCount",
                    "fieldsOfStudy",
                    "publicationTypes",
                    "openAccessPdf",
                ]
            )
        }
        headers = {}
        if self.settings.semantic_scholar_api_key:
            headers["x-api-key"] = self.settings.semantic_scholar_api_key
        data = self.http.get(
            f"{SEMANTIC_SCHOLAR_PAPER_URL}/DOI:{quote(clean_doi, safe='')}",
            params=params,
            headers=headers,
        )
        return self._parse_paper(data, include_raw)

    def _parse_paper(self, item: dict[str, Any], include_raw: bool) -> Paper:
        external_ids = item.get("externalIds") or {}
        open_access = item.get("openAccessPdf") or {}
        tldr = item.get("tldr") or {}
        abstract = _clean_text(item.get("abstract"))
        tldr_text = _clean_text(tldr.get("text"))
        return Paper(
            id=item.get("paperId") or str(item.get("corpusId") or ""),
            title=item.get("title") or "",
            abstract=abstract,
            abstract_en_raw=abstract,
            summary=tldr_text or abstract,
            authors=[author.get("name", "") for author in item.get("authors", []) if author.get("name")],
            year=item.get("year"),
            venue=item.get("venue"),
            doi=_clean_doi(external_ids.get("DOI")),
            url=item.get("url"),
            source="semantic_scholar",
            source_ids={key: str(value) for key, value in external_ids.items() if value},
            citation_count=item.get("citationCount"),
            fields_of_study=item.get("fieldsOfStudy") or [],
            concepts=[],
            open_access_pdf=open_access.get("url") if isinstance(open_access, dict) else None,
            landing_page_url=item.get("url"),
            abstract_source="semantic_scholar.abstract" if abstract else None,
            has_full_abstract=bool(abstract),
            raw=item if include_raw else None,
        )
