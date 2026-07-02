from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


Provider = Literal["openalex", "semantic_scholar"]
SortMode = Literal["relevance", "citation_count", "year"]


class Paper(BaseModel):
    id: str
    title: str
    abstract: str | None = None
    abstract_en_raw: str | None = None
    summary: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    source: Provider
    source_ids: dict[str, str] = Field(default_factory=dict)
    citation_count: int | None = None
    fields_of_study: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    open_access_pdf: str | None = None
    landing_page_url: str | None = None
    abstract_source: str | None = None
    has_full_abstract: bool = False
    raw: dict[str, Any] | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Keyword string or research direction.")
    limit: int = Field(30, ge=1, le=200)
    providers: list[Provider] = Field(default_factory=lambda: ["openalex", "semantic_scholar"])
    dois: list[str] = Field(default_factory=list, description="Exact DOI lookup list. Uses DOI-resolved provider APIs.")
    exact_doi: bool = Field(False, description="Treat query as an exact DOI when it contains one.")
    year_from: int | None = Field(None, ge=1500, le=2100)
    year_to: int | None = Field(None, ge=1500, le=2100)
    sort: SortMode = "relevance"
    require_abstract: bool = True
    semantic_search: bool = False
    include_raw: bool = False

    @field_validator("providers")
    @classmethod
    def providers_must_not_be_empty(cls, value: list[Provider]) -> list[Provider]:
        if not value:
            raise ValueError("At least one provider must be selected.")
        return value


class SearchResponse(BaseModel):
    query: str
    total: int
    papers: list[Paper]
    providers: list[Provider]


class ToolInfo(BaseModel):
    name: str
    description: str
    openapi_url: str
    endpoints: dict[str, str]
