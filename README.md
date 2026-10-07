# Industry Monitor Core

Shared, domain-neutral building blocks for business-unit industry monitors.

The platform layer has two deliberately separate responsibilities:

- this package provides basic public-information collection mechanics;
- `Business-Unit-for-Stock/stock-research` provides securities, ETF, and market
  data independently.

Energy, AI, and any future business unit own their own industry source lists
and industry interpretation on top of this package. No industry repository
inherits a stock or ETF collector from the platform layer.

This package contains no source registries, company lists, credentials, report
titles, or business-unit data. A domain project owns its own configuration and
public-report policy.

Current shared capability:

- safety-bounded HTTP client, URL/date/text helpers, reviewed link discovery,
  and bounded HTML article extraction
- configuration-driven fact, event, relationship, and industry-chain
  annotations with bounded daily signal aggregation

The package deliberately does not collect securities, ETFs, prices, or other
market data. Financial research belongs to the stock-research repository.
Industry intelligence is bounded: the package matches labels from a
business-owned taxonomy and aggregates observed articles. It does not infer
causality, market size, rankings, or investment conclusions.

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

Business repositories own source registries, company lists, financial inputs,
publication policy, and deployment. The core package must remain reusable and
domain-neutral.
