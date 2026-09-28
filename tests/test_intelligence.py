import json
import tempfile
import unittest
from pathlib import Path

from industry_monitor_core.intelligence import (
    aggregate_signals,
    annotate_article,
    load_intelligence_registry,
    public_intelligence,
)


REGISTRY = {
    "schema_version": 1,
    "domain": "sample",
    "reviewed_on": "2026-09-28",
    "evidence_levels": {"research": "研究机构发布"},
    "event_types": [
        {"id": "research", "label": "研究进展", "match_terms": ["研究", "实验"]},
    ],
    "chain_stages": [
        {"id": "platform", "label": "平台与工具", "match_terms": ["平台", "工具"]},
    ],
    "technology_tags": [
        {"id": "model", "label": "模型算法", "match_terms": ["模型", "算法"]},
    ],
    "application_scenarios": [
        {"id": "industry", "label": "工业应用", "match_terms": ["工业", "工厂"]},
    ],
    "entities": [
        {
            "id": "sample-lab",
            "label": "样例研究院",
            "entity_type": "research_org",
            "match_terms": ["样例研究院"],
        },
    ],
}


class IntelligenceTests(unittest.TestCase):
    def test_registry_and_annotation_build_traceable_relations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intelligence.json"
            path.write_text(json.dumps(REGISTRY, ensure_ascii=False), encoding="utf-8")
            config = load_intelligence_registry(path, "sample")
        article = annotate_article(
            {
                "url": "https://example.org/article",
                "title": "样例研究院发布工业模型平台",
                "publisher": "样例研究院",
                "kind": "research",
                "text": "研究团队发布模型算法工具，覆盖工厂应用，投入 10 万元。",
                "topics": [],
            },
            config,
        )
        intelligence = article["intelligence"]
        self.assertEqual(intelligence["primary_event_type"]["id"], "research")
        self.assertEqual(intelligence["chain_stages"][0]["id"], "platform")
        self.assertEqual(intelligence["entities"][0]["entity_type"], "research_org")
        self.assertTrue(intelligence["evidence"]["has_quantified_claim"])
        self.assertTrue(any(item["predicate"] == "addresses" for item in intelligence["relations"]))
        self.assertEqual(public_intelligence(article)["domain"], "sample")

    def test_aggregate_signals_counts_articles_and_limits_examples(self):
        article = {
            "title": "文章一",
            "url": "https://example.org/1",
            "intelligence": {
                "chain_stages": [{"id": "platform", "label": "平台与工具"}],
                "application_scenarios": [],
                "technology_tags": [],
                "event_types": [],
                "entities": [],
            },
        }
        result = aggregate_signals([article, {**article, "title": "文章二"}])
        self.assertEqual(result["article_count"], 2)
        self.assertEqual(result["chain_stages"][0]["article_count"], 2)
        self.assertEqual(len(result["chain_stages"][0]["examples"]), 2)

    def test_registry_rejects_foreign_domain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intelligence.json"
            path.write_text(json.dumps(REGISTRY), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_intelligence_registry(path, "energy")


if __name__ == "__main__":
    unittest.main()
