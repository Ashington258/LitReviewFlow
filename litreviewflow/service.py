from __future__ import annotations

from .clients import HttpClient, OpenAlexClient, SemanticScholarClient, extract_doi
from .config import Settings, load_settings
from .models import Paper, SearchRequest, SearchResponse


class LiteratureService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.http = HttpClient(self.settings)
        self.openalex = OpenAlexClient(self.http, self.settings)
        self.semantic_scholar = SemanticScholarClient(self.http, self.settings)

    def search(self, request: SearchRequest) -> SearchResponse:
        papers: list[Paper] = []
        per_provider_limit = request.limit
        errors: list[str] = []
        doi_queries = request.dois[:]
        if request.exact_doi:
            doi = extract_doi(request.query)
            if not doi:
                raise ValueError(f"exact_doi was requested, but query does not contain a DOI: {request.query}")
            doi_queries.append(doi)

        if doi_queries:
            for doi in doi_queries[: request.limit]:
                if "openalex" in request.providers:
                    try:
                        papers.append(self.openalex.lookup_doi(doi, include_raw=request.include_raw))
                    except Exception as exc:
                        errors.append(f"openalex DOI {doi}: {exc}")
                if "semantic_scholar" in request.providers:
                    try:
                        papers.append(self.semantic_scholar.lookup_doi(doi, include_raw=request.include_raw))
                    except Exception as exc:
                        errors.append(f"semantic_scholar DOI {doi}: {exc}")

            deduped = self._dedupe(papers)
            response = SearchResponse(
                query=request.query,
                total=min(len(deduped), request.limit),
                papers=deduped[: request.limit],
                providers=request.providers,
            )
            if not response.papers and errors:
                raise RuntimeError("; ".join(errors))
            return response

        if "openalex" in request.providers:
            try:
                papers.extend(
                    self.openalex.search(
                        query=request.query,
                        limit=per_provider_limit,
                        year_from=request.year_from,
                        year_to=request.year_to,
                        sort=request.sort,
                        require_abstract=request.require_abstract,
                        semantic_search=request.semantic_search,
                        include_raw=request.include_raw,
                    )
                )
            except Exception as exc:
                errors.append(f"openalex: {exc}")

        if "semantic_scholar" in request.providers:
            try:
                papers.extend(
                    self.semantic_scholar.search(
                        query=request.query,
                        limit=per_provider_limit,
                        year_from=request.year_from,
                        year_to=request.year_to,
                        sort=request.sort,
                        require_abstract=request.require_abstract,
                        include_raw=request.include_raw,
                    )
                )
            except Exception as exc:
                errors.append(f"semantic_scholar: {exc}")

        deduped = self._dedupe(papers)
        if request.sort == "citation_count":
            deduped.sort(key=lambda paper: paper.citation_count or 0, reverse=True)
        elif request.sort == "year":
            deduped.sort(key=lambda paper: paper.year or 0, reverse=True)

        response = SearchResponse(
            query=request.query,
            total=min(len(deduped), request.limit),
            papers=deduped[: request.limit],
            providers=request.providers,
        )
        if not response.papers and errors:
            raise RuntimeError("; ".join(errors))
        return response

    @staticmethod
    def _dedupe(papers: list[Paper]) -> list[Paper]:
        seen: set[str] = set()
        output: list[Paper] = []
        for paper in papers:
            key = ""
            if paper.doi:
                key = f"doi:{paper.doi.lower()}"
            elif paper.title and paper.year:
                key = f"title:{paper.title.strip().lower()}:{paper.year}"
            elif paper.id:
                key = f"{paper.source}:{paper.id}"
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            output.append(paper)
        return output
