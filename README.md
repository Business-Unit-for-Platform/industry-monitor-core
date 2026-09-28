# Industry Monitor Core

Shared, domain-neutral building blocks for business-unit industry monitors.

This package contains no source registries, company lists, credentials, report
titles, or business-unit data. A domain project owns its own configuration and
public-report policy.

Current shared capability:

- safety-bounded HTTP client, URL/date/text helpers, reviewed link discovery,
  and bounded HTML article extraction
- reviewed AKShare ETF history adapter with a Sina fallback when the primary
  Eastmoney history endpoint is unavailable
- bounded normalization of public daily market rows
- configurable ETF observation registry validation

The package deliberately does not decide whether an ETF is relevant to a
business domain, make investment recommendations, or publish a report.

## Architecture boundary

The package is the platform layer. It owns reusable mechanics and safety
controls only. Business repositories own source registries, keywords,
companies, topics, historical backfill rules, domain indicators, report
wording, Pages, and delivery targets. Raw pages, databases, credentials, and
notification ledgers never enter this public package.

The web API is dependency-inverted: callers pass a reviewed source mapping
and choose their own policy around it. The core refuses credentials, IP/private
hosts, HTTPS downgrade, unreviewed redirects, robots blocks, challenge pages,
restricted archives, unsupported media, and oversized responses. Attachments
are recorded as links and are not downloaded.

The two current business repositories may retain compatibility wrappers while
they migrate to this package. New business logic must not be added to those
wrappers.
