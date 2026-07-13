---
name: litreviewflow-search
description: Search scholarly papers through a LitReviewFlow checkout using OpenAlex and Semantic Scholar, returning titles, DOI, URLs, years, authors, abstracts, and optional bilingual abstract fields. Use when the user asks to find literature, recent research, DOI lists, article abstracts, literature review sources, OpenAlex or Semantic Scholar retrieval, or direct paper searches with abstracts.
---

# LitReviewFlow Search

## Project Discovery

Run commands from the LitReviewFlow repository root whenever possible. Identify it by the presence of both `scripts/search_literature.py` and the `litreviewflow/` package.

For the bundled wrapper, resolve the repository in this order:

1. `--project-root <path>`
2. `LITREVIEWFLOW_HOME`
3. The current directory or one of its parents
4. The repository containing this skill, when the skill is used directly from `.codex/skills/`

Never embed a machine-specific absolute path in commands, reports, or skill files.

## Workflow

1. Interpret the request:

- For latest or recent progress, use a recent year range.
- For introductions or foundational reviews, broaden the range.
- For an English or original abstract, include the retrieved English abstract when appropriate.
- For a Chinese abstract, provide a Chinese translation or paraphrase.
- For bilingual output, retain the retrieved English abstract and add a Chinese translation or paraphrase. Save large result sets to Markdown or JSON.

2. Run the CLI from the repository root:

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

3. Prefer these defaults unless the user specifies otherwise:

- `limit`: 8-10 per query
- `providers`: `openalex` for large retrieval; `openalex,semantic_scholar` for targeted retrieval or gap filling
- `year_from`: 2024 only for recent requests; use broader ranges for reviews
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

## Output

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

Read [references/api.md](references/api.md) when HTTP request and response details are needed.
