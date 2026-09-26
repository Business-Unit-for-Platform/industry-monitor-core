import unittest
from datetime import date

from industry_monitor_core.web import Page, canonical_url, discover, extract, parse_date


class WebCoreTests(unittest.TestCase):
    def test_canonical_url_removes_tracking_and_supports_domain_path_policy(self):
        value = "HTTPS://Example.com/a/../b/?utm_source=x&b=2&a=1"
        self.assertEqual(canonical_url(value), "https://example.com/a/../b/?a=1&b=2")
        self.assertEqual(canonical_url(value, normalize_path=True), "https://example.com/b/?a=1&b=2")

    def test_rejects_private_or_credentialed_urls(self):
        for value in ("http://127.0.0.1/a", "https://u:p@example.com/a", "http://x.local/a"):
            with self.assertRaises(ValueError):
                canonical_url(value)

    def test_parse_date_is_conservative(self):
        self.assertEqual(parse_date("发布时间：2026年9月25日"), "2026-09-25")
        self.assertIsNone(parse_date("没有日期"))

    def test_discover_uses_domain_keywords_and_reviewed_host(self):
        html = """<html><body>
        <a href='/a/20260925/one.html'>节能设备更新</a>
        <a href='/a/20260924/two.html'>无关内容</a>
        <a href='https://other.example/t.html'>人工智能</a>
        </body></html>""".encode()
        page = Page("https://example.com/list", 200, "text/html", html)
        source = {
            "entry_type": "listing", "link_selector": "a[href]",
            "article_pattern": r"/a/\d{8}/.*\.html$", "url": page.url,
            "allowed_hosts": ["example.com"], "name": "测试", "keywords": ["节能"],
        }
        self.assertEqual(
            discover(page, source)[0]["url"],
            "https://example.com/a/20260925/one.html",
        )

    def test_extract_keeps_attachment_as_link_only(self):
        html = (
            "<html><head><meta property='og:title' content='测试文章'>"
            "<meta property='article:published_time' content='2026-09-25'></head>"
            "<body><main>"
            + ("这是正文。" * 40)
            + "<a href='/file.pdf'>附件</a></main></body></html>"
        ).encode()
        page = Page("https://example.com/a/20260925/one.html", 200, "text/html", html)
        source = {
            "id": "sample", "publisher": "测试来源", "kind": "research",
            "region": "全国", "topics": ["样例"], "body_selectors": ["main"],
            "allowed_hosts": ["example.com"], "url": "https://example.com/",
        }
        result = extract(page, source)
        self.assertEqual(result["published_date"], date(2026, 9, 25).isoformat())
        self.assertEqual(result["attachments"][0]["status"], "link_only_not_read")
