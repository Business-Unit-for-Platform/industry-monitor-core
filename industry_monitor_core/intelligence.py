"""Domain-neutral industry intelligence annotations.

The module turns a business-owned taxonomy into bounded, traceable labels.
It deliberately does not infer market size, causality, ranking, or investment
advice.  Business repositories own the vocabulary and the source policy.
"""

import json
import re
from pathlib import Path


SCHEMA_VERSION = 1
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
NUMBER_PATTERN = re.compile(r"(?<![\w])(?:\d+(?:\.\d+)?|\.\d+)(?:%|万|亿|吨|MW|GW|kW|元|美元)?")

TAXONOMY_KEYS = (
    "event_types",
    "chain_stages",
    "technology_tags",
    "application_scenarios",
)


def _validate_items(config, key, required_terms=True):
    items = config.get(key)
    if not isinstance(items, list) or not items:
        raise ValueError(f"Intelligence registry needs a nonempty {key} list")
    identifiers = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{key} entries must be objects")
        identifier = item.get("id")
        label = item.get("label")
        if (
            not isinstance(identifier, str)
            or not ID_PATTERN.fullmatch(identifier)
            or identifier in identifiers
        ):
            raise ValueError(f"Invalid or duplicate {key} ID")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"{key} entry needs a label")
        terms = item.get("match_terms")
        if required_terms and (
            not isinstance(terms, list)
            or not terms
            or any(not isinstance(term, str) or not term.strip() for term in terms)
        ):
            raise ValueError(f"{key} entry needs nonempty match_terms")
        identifiers.add(identifier)
    return items


def load_intelligence_registry(path, expected_domain):
    """Load and validate a business-owned intelligence taxonomy."""
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported intelligence registry schema")
    if config.get("domain") != expected_domain:
        raise ValueError("Intelligence registry belongs to another domain")
    if not isinstance(config.get("reviewed_on"), str) or not config["reviewed_on"].strip():
        raise ValueError("Intelligence registry needs reviewed_on")
    for key in TAXONOMY_KEYS:
        _validate_items(config, key)
    entities = config.get("entities", [])
    if not isinstance(entities, list):
        raise ValueError("Intelligence entities must be a list")
    if entities:
        _validate_items({**config, "entities": entities}, "entities")
        for item in entities:
            if not isinstance(item.get("entity_type"), str) or not item["entity_type"].strip():
                raise ValueError("Intelligence entity needs entity_type")
    evidence_levels = config.get("evidence_levels")
    if not isinstance(evidence_levels, dict) or not evidence_levels:
        raise ValueError("Intelligence registry needs evidence_levels")
    if any(
        not isinstance(key, str) or not key.strip()
        or not isinstance(value, str) or not value.strip()
        for key, value in evidence_levels.items()
    ):
        raise ValueError("Intelligence evidence_levels must contain nonempty strings")
    return config


def _matches(text, item):
    folded = text.casefold()
    return any(term.casefold() in folded for term in item.get("match_terms", []))


def _matched(items, text):
    return [
        {"id": item["id"], "label": item["label"]}
        for item in items
        if _matches(text, item)
    ]


def _relation(subject_type, subject_ref, predicate, object_type, obj):
    return {
        "subject_type": subject_type,
        "subject_ref": subject_ref,
        "predicate": predicate,
        "object_type": object_type,
        "object_id": obj["id"],
        "object_label": obj["label"],
    }


def annotate_article(article, registry):
    """Attach bounded fact, relation, and taxonomy fields to an article."""
    text = " ".join(
        str(article.get(key, ""))
        for key in ("title", "publisher", "region", "text", "excerpt")
    )
    text += " " + " ".join(str(value) for value in article.get("topics", []))
    event_types = _matched(registry["event_types"], text)
    chain_stages = _matched(registry["chain_stages"], text)
    technology_tags = _matched(registry["technology_tags"], text)
    application_scenarios = _matched(registry["application_scenarios"], text)
    entities = _matched(registry.get("entities", []), text)
    entity_types = {
        item["id"]: item["entity_type"] for item in registry.get("entities", [])
    }
    article_ref = str(article.get("url", ""))
    relations = []
    for event in event_types:
        relations.append(_relation("article", article_ref, "reports", "event", event))
    for stage in chain_stages:
        relations.append(_relation("article", article_ref, "maps_to", "chain_stage", stage))
    for scenario in application_scenarios:
        relations.append(_relation("article", article_ref, "addresses", "scenario", scenario))
    for entity in entities:
        relations.append({
            "subject_type": "entity",
            "subject_ref": entity["id"],
            "predicate": "appears_in",
            "object_type": "article",
            "object_id": article_ref,
            "object_label": article.get("title", ""),
        })

    kind = str(article.get("kind", "unknown"))
    intelligence = {
        "schema_version": SCHEMA_VERSION,
        "domain": registry["domain"],
        "event_types": event_types,
        "primary_event_type": event_types[0] if event_types else None,
        "chain_stages": chain_stages,
        "technology_tags": technology_tags,
        "application_scenarios": application_scenarios,
        "entities": [
            {**entity, "entity_type": entity_types[entity["id"]]}
            for entity in entities
        ],
        "relations": relations,
        "evidence": {
            "level": registry["evidence_levels"].get(kind, "公开资料"),
            "source_kind": kind,
            "published_date": article.get("published_date"),
            "has_quantified_claim": bool(NUMBER_PATTERN.search(text)),
        },
    }
    return {**article, "intelligence": intelligence}


def public_intelligence(article):
    """Return the public allowlist for an annotated article."""
    value = article.get("intelligence") or {}
    if not isinstance(value, dict):
        return None
    fields = (
        "schema_version",
        "domain",
        "event_types",
        "primary_event_type",
        "chain_stages",
        "technology_tags",
        "application_scenarios",
        "entities",
        "relations",
        "evidence",
    )
    result = {key: value[key] for key in fields if key in value}
    if not result.get("schema_version") or not result.get("domain"):
        return None
    return result


def _examples(articles):
    return [
        {
            "title": str(article.get("title", ""))[:120],
            "published_date": article.get("published_date"),
            "url": article.get("url"),
        }
        for article in articles[:3]
    ]


def aggregate_signals(articles):
    """Aggregate observed labels without turning counts into trend claims."""
    buckets = {
        "chain_stages": {},
        "application_scenarios": {},
        "technology_tags": {},
        "event_types": {},
        "entities": {},
    }
    for article in articles:
        intelligence = article.get("intelligence") or {}
        for key in buckets:
            for item in intelligence.get(key, []):
                identifier = item.get("id")
                if not identifier:
                    continue
                bucket = buckets[key].setdefault(
                    identifier,
                    {"id": identifier, "label": item.get("label", identifier), "articles": []},
                )
                bucket["articles"].append(article)
    result = {
        "schema_version": SCHEMA_VERSION,
        "article_count": len(articles),
    }
    for key, values in buckets.items():
        result[key] = [
            {
                "id": value["id"],
                "label": value["label"],
                "article_count": len(value["articles"]),
                "examples": _examples(value["articles"]),
            }
            for value in sorted(
                values.values(),
                key=lambda item: (-len(item["articles"]), item["label"]),
            )
        ]
    return result
