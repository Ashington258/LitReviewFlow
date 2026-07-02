from litreviewflow.clients import extract_doi, reconstruct_openalex_abstract
from litreviewflow.models import Paper, SearchRequest
from litreviewflow.service import LiteratureService


def test_reconstruct_openalex_abstract() -> None:
    inverted = {"Large": [0], "language": [1], "models": [2], "work.": [3]}
    assert reconstruct_openalex_abstract(inverted) == "Large language models work."


def test_dedupe_prefers_doi() -> None:
    papers = [
        Paper(id="a", title="Same", doi="10.1/example", source="openalex"),
        Paper(id="b", title="Same", doi="10.1/example", source="semantic_scholar"),
    ]
    assert len(LiteratureService._dedupe(papers)) == 1


def test_extract_doi_from_plain_or_url() -> None:
    assert extract_doi("10.1117/1.2399537") == "10.1117/1.2399537"
    assert extract_doi("https://doi.org/10.1364/OE.19.019384.") == "10.1364/oe.19.019384"


def test_service_exact_doi_lookup_uses_provider_lookup(monkeypatch) -> None:
    service = LiteratureService()

    def fake_lookup_doi(doi: str, include_raw: bool) -> Paper:
        return Paper(
            id="https://openalex.org/W1",
            title="Exact DOI Paper",
            doi=doi,
            source="openalex",
            abstract="English abstract",
            abstract_en_raw="English abstract",
        )

    def fail_search(*args, **kwargs):
        raise AssertionError("keyword search should not be used for exact DOI lookup")

    monkeypatch.setattr(service.openalex, "lookup_doi", fake_lookup_doi)
    monkeypatch.setattr(service.openalex, "search", fail_search)
    response = service.search(
        SearchRequest(
            query="10.1117/1.2399537",
            providers=["openalex"],
            exact_doi=True,
            limit=1,
        )
    )

    assert response.total == 1
    assert response.papers[0].title == "Exact DOI Paper"
    assert response.papers[0].abstract_en_raw == "English abstract"
