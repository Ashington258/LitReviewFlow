# LitReviewFlow API Reference

Run commands from the repository root. See the project-discovery rules in `SKILL.md` when the checkout location is unknown.

## CLI

```powershell
python scripts/search_literature.py "<query>" --limit 10 --year-from 2024 --year-to 2026 --semantic-search
```

## HTTP

```text
GET http://127.0.0.1:8000/ai/literature/search?query=<query>&limit=10&year_from=2024&year_to=2026&semantic_search=true
POST http://127.0.0.1:8000/papers/search
GET http://127.0.0.1:8000/openapi.json
```

POST body:

```json
{
  "query": "field-oriented control FOC PMSM motor drive",
  "limit": 10,
  "providers": ["openalex", "semantic_scholar"],
  "year_from": 2024,
  "year_to": 2026,
  "sort": "relevance",
  "require_abstract": true,
  "semantic_search": true,
  "include_raw": false
}
```
