"""Domain-neutral adapters for industry monitoring projects."""

from .akshare_etf import (
    AkshareFetchError,
    AkshareUnavailable,
    fetch_history,
    market_observation,
    normalize_history,
)
from .registry import load_market_registry
from .web import (
    FetchError,
    Page,
    SafeClient,
    canonical_url,
    date_hint,
    digest,
    discover,
    excerpt,
    extract,
    markdown_text,
    meta_content,
    normalize_text,
    now,
    parse_date,
    source_link,
)

__all__ = [
    "AkshareFetchError",
    "AkshareUnavailable",
    "fetch_history",
    "load_market_registry",
    "market_observation",
    "normalize_history",
    "FetchError",
    "Page",
    "SafeClient",
    "canonical_url",
    "date_hint",
    "digest",
    "discover",
    "excerpt",
    "extract",
    "markdown_text",
    "meta_content",
    "normalize_text",
    "now",
    "parse_date",
    "source_link",
]
