"""Domain-neutral, safety-bounded web collection primitives.

The caller owns source registries, keywords, selectors and business policy.
This module only provides the mechanics shared by industry monitors.
"""

import hashlib
import ipaddress
import posixpath
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup, UnicodeDammit


LOCAL_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
DEFAULT_USER_AGENT = "IndustryMonitorCore/0.1"
TRACKING_PARAMETERS = {"fbclid", "gclid", "spm"}


class FetchError(RuntimeError):
    """Raised when a reviewed fetch cannot safely be completed."""


@dataclass
class Page:
    """A bounded HTTP response captured without executing page content."""

    url: str
    status: int
    content_type: str
    payload: bytes
    x_robots: str = ""

    @property
    def html(self):
        try:
            return self.payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            decoded = UnicodeDammit(self.payload, is_html=True).unicode_markup
            if decoded is None:
                raise FetchError("Unable to decode page")
            return decoded


def now():
    return datetime.now(LOCAL_TZ).isoformat(timespec="seconds")


def digest(value):
    data = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical_url(url, normalize_path=False):
    """Normalize a public HTTP(S) URL and reject unsafe address forms."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Only absolute HTTP(S) URLs are supported")
    if parts.username or parts.password:
        raise ValueError("Credentials are not allowed in URLs")
    if parts.port not in (None, 80, 443):
        raise ValueError("Nonstandard ports are not supported")
    host = parts.hostname.lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP address sources are not supported")
    if "." not in host or host.endswith((".local", ".localhost", ".internal")):
        raise ValueError("Local/private hostnames are not supported")
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS
    )
    path = parts.path or "/"
    if normalize_path:
        path = posixpath.normpath(path)
        if parts.path.endswith("/") and not path.endswith("/"):
            path += "/"
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(query), ""))


class SafeClient:
    """Fetch reviewed hosts with robots, TLS, redirect and size controls."""

    def __init__(
        self,
        delay=2.0,
        timeout=12,
        max_bytes=2_000_000,
        session=None,
        user_agent=DEFAULT_USER_AGENT,
        normalize_paths=False,
    ):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.delay = delay
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.last_request = {}
        self.robot_cache = {}
        self.user_agent = user_agent
        self.normalize_paths = normalize_paths

    def _allowed(self, url, source):
        url = canonical_url(url, normalize_path=self.normalize_paths)
        allowed = set(source.get("allowed_hosts", [urlsplit(source["url"]).hostname]))
        if urlsplit(url).hostname not in allowed:
            raise FetchError("Host outside the reviewed source allowlist")
        if urlsplit(source["url"]).scheme == "https" and urlsplit(url).scheme != "https":
            raise FetchError("HTTPS downgrade refused")
        return url

    def _raw(self, url, delay=None):
        host = urlsplit(url).hostname
        wait = max(self.delay, delay or 0) - (
            time.monotonic() - self.last_request.get(host, 0)
        )
        if wait > 0:
            time.sleep(wait)
        self.last_request[host] = time.monotonic()
        try:
            with self.session.get(
                url, timeout=self.timeout, allow_redirects=False, stream=True
            ) as response:
                payload = bytearray()
                for chunk in response.iter_content(chunk_size=32768):
                    payload.extend(chunk)
                    if len(payload) > self.max_bytes:
                        raise FetchError("Response exceeds the configured size limit")
                return (
                    Page(
                        url,
                        response.status_code,
                        response.headers.get("Content-Type", ""),
                        bytes(payload),
                        response.headers.get("X-Robots-Tag", ""),
                    ),
                    response.headers.get("Location"),
                )
        except requests.RequestException as error:
            raise FetchError(f"Network/TLS failure: {type(error).__name__}") from error

    def robots(self, url):
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self.robot_cache:
            try:
                page, _ = self._raw(origin + "/robots.txt")
                if page.status in (404, 410):
                    result = {"status": "missing", "detail": f"HTTP {page.status}", "parser": None}
                elif page.status != 200:
                    result = {"status": "blocked", "detail": f"robots HTTP {page.status}", "parser": None}
                elif re.search(r"<(?:html|!doctype)", page.html, re.I):
                    result = {"status": "blocked", "detail": "robots returned HTML/challenge", "parser": None}
                elif re.search(r"(?im)^\s*(?:allow|disallow)\s*:[^\r\n]*[*$]", page.html):
                    result = {
                        "status": "blocked",
                        "detail": "robots wildcard rules require a reviewed RFC-compatible adapter",
                        "parser": None,
                    }
                else:
                    parser = RobotFileParser(origin + "/robots.txt")
                    parser.parse(page.html.splitlines())
                    result = {"status": "parsed", "detail": "robots parsed", "parser": parser}
            except FetchError as error:
                result = {"status": "blocked", "detail": str(error), "parser": None}
            self.robot_cache[origin] = result
        result = self.robot_cache[origin]
        if result["status"] == "blocked":
            raise FetchError(result["detail"])
        parser = result["parser"]
        if parser and not parser.can_fetch(self.user_agent, url):
            raise FetchError("robots disallows this URL")
        return result["detail"], parser.crawl_delay(self.user_agent) if parser else None

    def fetch(self, url, source, content_types=None):
        content_types = content_types or ("text/html", "application/xhtml+xml")
        current = self._allowed(url, source)
        for _ in range(5):
            _, delay = self.robots(current)
            page, location = self._raw(current, delay=delay)
            if page.status in (301, 302, 303, 307, 308):
                if not location:
                    raise FetchError("Redirect without Location")
                current = self._allowed(urljoin(current, location), source)
                continue
            if page.status != 200:
                raise FetchError(f"Page HTTP {page.status}; no bypass or immediate retry")
            media_type = page.content_type.split(";", 1)[0].strip().lower()
            if media_type not in content_types:
                raise FetchError("Response media type outside the reviewed adapter")
            if any(rule in page.x_robots.lower() for rule in ("noarchive", "nosnippet", "max-snippet:0")):
                raise FetchError("Archive/snippet restriction; manual review required")
            title = BeautifulSoup(page.html, "html.parser").title
            if title and re.search(
                r"captcha|access denied|just a moment|验证|访问受限|forbidden",
                title.get_text(),
                re.I,
            ):
                raise FetchError("Challenge/login page; manual review required")
            return page
        raise FetchError("Redirect limit reached")


def normalize_text(text):
    return re.sub(r"\s+", " ", text).strip()


def meta_content(soup, names):
    names = {name.lower() for name in names}
    for node in soup.find_all("meta"):
        if (node.get("name") or node.get("property") or "").lower() in names and node.get("content"):
            return node["content"].strip()
    return None


def parse_date(text):
    if not text:
        return None
    match = re.search(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})", text)
    if not match:
        return None
    try:
        return date(*map(int, match.groups())).isoformat()
    except ValueError:
        return None


def date_hint(url):
    match = re.search(r"/(?:t)?(20\d{2})(\d{2})(\d{2})(?:_|/)", urlsplit(url).path)
    return parse_date("-".join(match.groups())) if match else None


def source_link(url, base, source, normalize_path=False):
    url = canonical_url(urljoin(base, url), normalize_path=normalize_path)
    parts = urlsplit(url)
    if parts.hostname not in source.get("allowed_hosts", []):
        raise ValueError("Link outside reviewed hosts")
    if urlsplit(source["url"]).scheme == "https" and parts.scheme != "https":
        if not source.get("upgrade_http_links"):
            raise ValueError("Insecure link refused")
        url = urlunsplit(("https", parts.netloc, parts.path, parts.query, ""))
    return url


def discover(page, source, default_keywords=(), normalize_path=False):
    """Discover article links using only the caller's reviewed source rules."""
    if source["entry_type"] == "article":
        return [{"url": canonical_url(page.url, normalize_path=normalize_path), "title": source["name"]}]
    soup = BeautifulSoup(page.html, "html.parser")
    restrictions = " ".join(
        [page.x_robots]
        + [node.get("content", "") for node in soup.select('meta[name="robots"]')]
    ).lower()
    if any(rule in restrictions for rule in ("noarchive", "nosnippet", "max-snippet:0")):
        raise FetchError("Listing archive/snippet restriction")
    anchors = soup.select(source.get("link_selector", "a[href]"))
    if source.get("link_selector") and not anchors:
        raise FetchError("Reviewed listing selector did not match")
    pattern = re.compile(source["article_pattern"])
    links = {}
    keywords = source.get("keywords", default_keywords)
    for anchor in anchors:
        title = normalize_text(anchor.get("title") or anchor.get_text(" ", strip=True))
        if not title or (not source.get("include_all_articles") and not any(word in title for word in keywords)):
            continue
        try:
            url = source_link(anchor["href"], page.url, source, normalize_path=normalize_path)
        except ValueError:
            continue
        if source.get("article_query_pattern") and not re.fullmatch(source["article_query_pattern"], urlsplit(url).query):
            continue
        if pattern.search(urlsplit(url).path):
            links.setdefault(url, {"url": url, "title": title})
    if len(links) > 100:
        raise FetchError("Listing exceeds reviewed link budget; refusing silent truncation")
    return sorted(links.values(), key=lambda item: date_hint(item["url"]) or "", reverse=True)


def extract(page, source, fallback_title="", normalize_path=False):
    """Extract a bounded article record while retaining only attachment links."""
    soup = BeautifulSoup(page.html, "html.parser")
    restrictions = " ".join(
        [page.x_robots]
        + [node.get("content", "") for node in soup.select('meta[name="robots"]')]
    ).lower()
    if any(rule in restrictions for rule in ("noarchive", "nosnippet", "max-snippet:0")):
        raise FetchError("Archive/snippet restriction; manual review required")
    title = meta_content(soup, ["ArticleTitle", "og:title", "DC.title"])
    if not title:
        for selector in source.get("title_selectors", []):
            heading = soup.select_one(selector)
            if heading and normalize_text(heading.get_text(" ", strip=True)):
                title = normalize_text(heading.get_text(" ", strip=True))
                break
    if not title:
        heading = soup.find("h1")
        title = normalize_text(heading.get_text(" ", strip=True)) if heading else ""
    title = title or fallback_title or (soup.title.get_text(strip=True) if soup.title else "")
    raw_date = meta_content(
        soup,
        ["PubDate", "PublishDate", "firstpublishedtime", "article:published_time", "DC.date.issued", "date"],
    )
    published = parse_date(raw_date)
    evidence = "publication metadata" if published else None
    if not published:
        for selector in source.get("date_selectors", []):
            for node in soup.select(selector):
                candidate = parse_date(node.get_text(" ", strip=True))
                if candidate:
                    published, evidence = candidate, f"publication selector: {selector}"
                    break
            if published:
                break
    body = None
    used_selector = None
    for selector in source["body_selectors"]:
        body = soup.select_one(selector)
        if body is not None:
            used_selector = selector
            break
    if body is None:
        raise FetchError("Reviewed body selector did not match; no whole-page fallback")
    for node in body.select("script,style,nav,footer,form,noscript"):
        node.decompose()
    text = normalize_text(body.get_text(" ", strip=True))
    if len(text) < 120 or text.count("\ufffd") > 3:
        raise FetchError("Body too short or decoding quality failed")
    attachments = []
    candidates = []
    attachment_scopes = [body]
    for selector in source.get("attachment_selectors", []):
        attachment_scopes.extend(soup.select(selector))
    seen_attachments = set()
    for scope in attachment_scopes:
        for anchor in scope.select("a[href]"):
            raw_url = urljoin(page.url, anchor["href"])
            parts = urlsplit(raw_url)
            if not re.search(r"\.(pdf|docx?|xlsx?|pptx?|zip)$", parts.path, re.I):
                continue
            if parts.scheme not in ("http", "https") or parts.username or parts.password:
                continue
            try:
                url = canonical_url(raw_url, normalize_path=normalize_path)
                status = "link_only_not_read"
            except ValueError:
                url, status = raw_url, "address_requires_review_not_fetched"
            if url not in seen_attachments:
                attachments.append({"url": url, "title": normalize_text(anchor.get_text(" ", strip=True))[:200], "status": status})
                seen_attachments.add(url)
    for anchor in body.select("a[href]"):
        try:
            url = canonical_url(urljoin(page.url, anchor["href"]), normalize_path=normalize_path)
        except ValueError:
            continue
        label = normalize_text(anchor.get_text(" ", strip=True))[:200]
        if url not in seen_attachments and urlsplit(url).hostname not in source.get("allowed_hosts", []):
            candidates.append({"url": url, "title": label, "discovered_from": page.url, "status": "pending_review"})
    return {
        "url": canonical_url(page.url, normalize_path=normalize_path),
        "title": title,
        "source_id": source["id"],
        "publisher": source["publisher"],
        "kind": source["kind"],
        "region": source["region"],
        "topics": source["topics"],
        "published_date": published,
        "date_evidence": evidence,
        "url_date_hint_unverified": date_hint(page.url),
        "text": text,
        "content_hash": digest(text),
        "raw_hash": digest(page.payload),
        "body_selector": used_selector,
        "attachments": attachments,
        "candidates": candidates,
        **({"edition": source["edition"]} if source.get("edition") is not None else {}),
    }


def excerpt(text, limit=260):
    """Create a short public excerpt and redact common phone-number shapes."""
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[电话已省略]", text)
    text = re.sub(r"(?<!\d)0\d{2,3}[-－ ]?\d{7,8}(?:[-转]\d{1,6})?(?!\d)", "[电话已省略]", text)
    if len(text) <= limit:
        return text
    prefix = text[:limit]
    stop = max(prefix.rfind("。"), prefix.rfind("；"), prefix.rfind("！"))
    if stop >= 60:
        return prefix[:stop + 1] + " [摘录，详见原文]"
    return prefix + " [截断摘录，请核对原文]"


def markdown_text(text):
    return re.sub(r"([\\`*_{}\[\]<>|])", r"\\\1", normalize_text(str(text)))
