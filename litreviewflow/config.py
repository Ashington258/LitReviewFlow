from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("config/config.json")


@dataclass(frozen=True)
class SearchDefaults:
    query: str = ""
    limit: int = 10
    providers: list[str] = field(default_factory=lambda: ["openalex", "semantic_scholar"])
    year_from: int | None = 2024
    year_to: int | None = 2026
    sort: str = "relevance"
    require_abstract: bool = True
    semantic_search: bool = True
    include_raw: bool = False


@dataclass(frozen=True)
class Settings:
    app_name: str = "LitReviewFlow"
    contact_email: str = ""
    openalex_api_key: str = ""
    semantic_scholar_api_key: str = ""
    request_timeout_seconds: int = 30
    request_delay_seconds: float = 0.3
    max_retries: int = 3
    host: str = "127.0.0.1"
    port: int = 8000
    search_defaults: SearchDefaults = field(default_factory=SearchDefaults)

    @property
    def user_agent(self) -> str:
        if self.contact_email:
            return f"{self.app_name}/0.1 (mailto:{self.contact_email})"
        return f"{self.app_name}/0.1"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a JSON object: {path}")
    return data


def load_settings(path: str | Path = DEFAULT_CONFIG_PATH) -> Settings:
    data = _read_json(Path(path))
    defaults = data.get("search_defaults") or {}
    if not isinstance(defaults, dict):
        raise ValueError("search_defaults must be a JSON object.")
    return Settings(
        app_name=str(data.get("app_name") or os.getenv("LITREVIEWFLOW_APP_NAME") or "LitReviewFlow"),
        contact_email=str(data.get("contact_email") or os.getenv("CONTACT_EMAIL") or ""),
        openalex_api_key=str(data.get("openalex_api_key") or os.getenv("OPENALEX_API_KEY") or ""),
        semantic_scholar_api_key=str(
            data.get("semantic_scholar_api_key") or os.getenv("SEMANTIC_SCHOLAR_API_KEY") or ""
        ),
        request_timeout_seconds=int(
            data.get("request_timeout_seconds") or os.getenv("REQUEST_TIMEOUT_SECONDS") or 30
        ),
        request_delay_seconds=float(data.get("request_delay_seconds") or os.getenv("REQUEST_DELAY_SECONDS") or 0.3),
        max_retries=int(data.get("max_retries") or os.getenv("MAX_RETRIES") or 3),
        host=str(data.get("host") or os.getenv("LITREVIEWFLOW_HOST") or "127.0.0.1"),
        port=int(data.get("port") or os.getenv("LITREVIEWFLOW_PORT") or 8000),
        search_defaults=SearchDefaults(
            query=str(defaults.get("query") or ""),
            limit=int(defaults.get("limit") or 10),
            providers=list(defaults.get("providers") or ["openalex", "semantic_scholar"]),
            year_from=defaults.get("year_from", 2024),
            year_to=defaults.get("year_to", 2026),
            sort=str(defaults.get("sort") or "relevance"),
            require_abstract=bool(defaults.get("require_abstract", True)),
            semantic_search=bool(defaults.get("semantic_search", True)),
            include_raw=bool(defaults.get("include_raw", False)),
        ),
    )
