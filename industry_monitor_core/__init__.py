"""Domain-neutral adapters for industry monitoring projects."""

from .intelligence import (
    aggregate_signals,
    annotate_article,
    load_intelligence_registry,
    public_intelligence,
)
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
    "aggregate_signals",
    "annotate_article",
    "load_intelligence_registry",
    "public_intelligence",
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
