---
name: litreviewflow-search
description: 'Search scholarly papers through a LitReviewFlow checkout using OpenAlex and Semantic Scholar. Use when: find literature, search papers, retrieve DOI metadata, get article abstracts, collect literature review sources, query OpenAlex or Semantic Scholar, run LitReviewFlow CLI or HTTP paper search with English, Chinese, or bilingual abstracts.'
argument-hint: '<query, DOI, or literature-search request>'
---

# LitReviewFlow Search

## What This Skill Does

Use this skill to search scholarly literature from a LitReviewFlow repository checkout. It guides Copilot to run the repository CLI or HTTP API and return paper titles, DOI values, URLs, years, authors, abstracts, and optional bilingual abstract fields.

## Project Discovery

Run commands from the LitReviewFlow repository root whenever possible. Identify the root by the presence of both `scripts/search_literature.py` and the `litreviewflow/` package.

Resolve the repository in this order:

1. A user-provided project path.
2. The `LITREVIEWFLOW_HOME` environment variable.
3. The current workspace folder or one of its parents.
4. The repository containing this skill when used from `.github/skills/`, `.agents/skills/`, or another copied skill folder.

Do not embed machine-specific absolute paths in commands, reports, or generated skill files.

## Workflow

1. Interpret the request.

- For latest or recent progress, use a recent year range.
- For introductions or foundational reviews, broaden the year range.
- For an English or original abstract, include the retrieved English abstract when appropriate.
- For a Chinese abstract, provide a Chinese translation or paraphrase.
- For bilingual output, retain the retrieved English abstract and add a Chinese translation or paraphrase.
- Save large result sets to Markdown or JSON instead of pasting long outputs into chat.

2. Run the CLI from the repository root.

```powershell
python scripts/search_literature.py "<query>" --limit 10
```

For exact DOI retrieval, use DOI mode:

```powershell
python scripts/search_literature.py --doi "10.1117/1.2399537" --providers openalex --output english
python scripts/search_literature.py --doi-file .\dois.txt --providers openalex --limit 50 --output bilingual
python scripts/search_literature.py "10.1117/1.2399537" --exact-doi --providers openalex --output english
```

Never pass a DOI as an ordinary keyword query when verifying a specific paper.

3. Prefer these defaults unless the user specifies otherwise.

- `limit`: 8-10 per query
- `providers`: `openalex` for large retrieval; `openalex,semantic_scholar` for targeted retrieval or gap filling
- `year_from`: 2024 only for recent requests; broader ranges for reviews
- `year_to`: current year
- `semantic_search`: true
- `require_abstract`: true

Recent-progress example:

```powershell
python scripts/search_literature.py "field-oriented control FOC motor drive PMSM induction motor latest advances" --limit 10 --year-from 2024 --year-to 2026 --semantic-search
```

4. For 30 or more papers:

- Split the search into topical batches.
- Start with `--providers openalex` to reduce timeout risk.
- Use `--sort citation_count` for foundational literature and relevance or year sorting for emerging work.
- Deduplicate by DOI, then normalized title.
- Filter false positives by title and abstract relevance.
- Retry OpenAlex semantic-search failures with `--no-semantic-search`, stricter terms, or a smaller limit.
- Use `--doi-file` to refill abstracts by exact DOI when candidate DOI values already exist.

5. Return title, year, DOI, source URL, and abstract. Rerun with stricter terms when results contain false positives.

## Output Rules

- Always include DOI and source URL when available.
- Save large literature sets to a project-relevant Markdown or JSON file.
- Avoid pasting excessive verbatim abstracts into chat.
- Use these output meanings:
  - `english`: retrieved `abstract_en_raw` or `abstract`
  - `zh`: agent-generated Chinese translation or paraphrase
  - `bilingual`: retrieved English plus agent-generated Chinese

## HTTP Interface

When the API server is running:

```text
GET http://127.0.0.1:8000/ai/literature/search?query=<urlencoded query>&limit=10&year_from=2024&year_to=2026&semantic_search=true
GET http://127.0.0.1:8000/ai/tools
GET http://127.0.0.1:8000/openapi.json
```

Start it from the repository root:

```powershell
python -m uvicorn litreviewflow.api:app --host 127.0.0.1 --port 8000
```

## Configuration

Use `config/config.json` relative to the repository root. Copy `config/config.example.json` when creating local configuration, keep API keys out of Git, and read `doc/使用文档.md` for setup or API details.

Read `references/api.md` when HTTP request and response details are needed and that file exists in the copied skill package.

## Completion Checks

- The repository root was identified before commands were run.
- DOI lookups used DOI mode, not ordinary keyword search.
- Results include title, year, DOI, source URL, and abstract when available.
- Large result sets were saved to a file.
- The final response states any provider failures, missing abstracts, or filtering decisions.