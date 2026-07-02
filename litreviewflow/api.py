from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query

from .config import load_settings
from .models import Provider, SearchRequest, SearchResponse, SortMode, ToolInfo
from .service import LiteratureService


app = FastAPI(
    title="LitReviewFlow API",
    version="0.1.0",
    description=(
        "Automated literature review search API. It indexes papers from OpenAlex and Semantic Scholar, "
        "normalizes metadata, and exposes abstracts/summaries for downstream AI agents."
    ),
)


def get_service() -> LiteratureService:
    return LiteratureService(load_settings())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ai/tools", response_model=ToolInfo)
def ai_tools() -> ToolInfo:
    return ToolInfo(
        name="litreviewflow",
        description="Search scholarly articles by keywords or research direction and return metadata plus abstracts.",
        openapi_url="/openapi.json",
        endpoints={
            "POST /papers/search": "Search papers and return normalized paper list with abstracts.",
            "GET /papers/search": "Convenience query-string version of the same search.",
            "GET /ai/literature/search": "AI-friendly search endpoint with concise JSON response.",
            "GET /ai/literature/doi": "Exact DOI lookup for one or more papers.",
        },
    )


@app.post("/papers/search", response_model=SearchResponse)
def search_papers(request: SearchRequest, service: LiteratureService = Depends(get_service)) -> SearchResponse:
    try:
        return service.search(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/papers/search", response_model=SearchResponse)
def search_papers_get(
    query: str = Query(..., min_length=1),
    limit: int = Query(30, ge=1, le=200),
    providers: list[Provider] = Query(default=["openalex", "semantic_scholar"]),
    dois: list[str] = Query(default=[]),
    exact_doi: bool = False,
    year_from: int | None = Query(None, ge=1500, le=2100),
    year_to: int | None = Query(None, ge=1500, le=2100),
    sort: SortMode = "relevance",
    require_abstract: bool = True,
    semantic_search: bool = False,
    include_raw: bool = False,
    service: LiteratureService = Depends(get_service),
) -> SearchResponse:
    request = SearchRequest(
        query=query,
        limit=limit,
        providers=providers,
        dois=dois,
        exact_doi=exact_doi,
        year_from=year_from,
        year_to=year_to,
        sort=sort,
        require_abstract=require_abstract,
        semantic_search=semantic_search,
        include_raw=include_raw,
    )
    return search_papers(request, service)


@app.get("/ai/literature/search")
def ai_literature_search(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    year_from: int | None = Query(None, ge=1500, le=2100),
    year_to: int | None = Query(None, ge=1500, le=2100),
    semantic_search: bool = False,
    service: LiteratureService = Depends(get_service),
) -> dict[str, object]:
    response = search_papers_get(
        query=query,
        limit=limit,
        providers=["openalex", "semantic_scholar"],
        year_from=year_from,
        year_to=year_to,
        sort="relevance",
        require_abstract=True,
        semantic_search=semantic_search,
        include_raw=False,
        service=service,
    )
    return {
        "query": response.query,
        "total": response.total,
        "papers": [
            {
                "title": paper.title,
                "year": paper.year,
                "authors": paper.authors,
                "doi": paper.doi,
                "url": paper.url,
                "source": paper.source,
                "citation_count": paper.citation_count,
                "abstract": paper.abstract,
                "abstract_en_raw": paper.abstract_en_raw,
                "summary": paper.summary,
                "open_access_pdf": paper.open_access_pdf,
            }
            for paper in response.papers
        ],
    }


@app.get("/ai/literature/doi")
def ai_literature_doi(
    doi: list[str] = Query(..., min_length=1),
    providers: list[Provider] = Query(default=["openalex"]),
    include_raw: bool = False,
    service: LiteratureService = Depends(get_service),
) -> dict[str, object]:
    response = search_papers_get(
        query="DOI lookup",
        limit=len(doi),
        providers=providers,
        dois=doi,
        exact_doi=False,
        year_from=None,
        year_to=None,
        sort="relevance",
        require_abstract=True,
        semantic_search=False,
        include_raw=include_raw,
        service=service,
    )
    return {
        "total": response.total,
        "papers": [
            {
                "title": paper.title,
                "year": paper.year,
                "authors": paper.authors,
                "doi": paper.doi,
                "url": paper.url,
                "source": paper.source,
                "citation_count": paper.citation_count,
                "abstract": paper.abstract,
                "abstract_en_raw": paper.abstract_en_raw,
                "summary": paper.summary,
                "open_access_pdf": paper.open_access_pdf,
            }
            for paper in response.papers
        ],
    }
