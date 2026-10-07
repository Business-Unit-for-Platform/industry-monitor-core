# Industry Monitor Core Architecture

`industry-monitor-core` is the shared platform foundation for business-unit
industry monitors. It is intentionally domain-neutral and public. In the
organization architecture, this is the basic public-information layer; stock
and ETF collection is a separate vertical owned by `stock-research`.

## Ownership

### Core package

- Safe HTTP collection: robots, TLS, reviewed-host allowlists, redirects,
  request spacing, response-size limits, and challenge-page rejection.
- URL normalization, date parsing, text cleanup, hashing, excerpts, and
  Markdown escaping.
- Generic page model, reviewed article-link discovery, bounded body extraction,
  attachment-link registration, and external-candidate registration.
- Domain-neutral industry intelligence annotations: event types, chain stages,
  technology tags, application scenarios, entities, relations, evidence
  levels, and bounded signal aggregation.

### Business-unit repository

- Source registries, keywords, host policy, selectors, and access review.
- Company lists, cities, regions, subjects, tags, indicators, and backfill
  adapters.
- SQLite schema migrations, raw archive location, daily aggregation, report
  wording, public-site layout, and notification payloads.
- Repository secrets, Pages domains, recipients, delivery ledgers, and CI
  deployment permissions.

## Dependency direction

```text
domain config / adapters
          |
          v
industry_monitor_core.web
          |
          v
industry_monitor_core.intelligence
          |
          v
domain archive -> domain report -> domain publication / notification
```

The core package never imports a business repository and never reads a source
registry, a credential, a domain data directory, or a market-data watchlist.
A third business unit should add configuration or a small domain adapter in
its own repository rather than copying a business repository's data or report
code. Securities and ETF collection belongs to stock-research.

Industry ownership is explicit:

```text
industry-monitor-core        basic web collection and bounded annotation
Business-Unit-for-Stock      stocks, ETFs, disclosures, and market research
Business-Unit-for-Energy...  energy-saving industry sources and taxonomy
Business-Unit-for-AI...      AI/computer industry sources and taxonomy
```

The core may be reused by several industry verticals, but it must never become
the source of truth for a vertical's source list. A vertical source entry,
keyword policy, company watchlist, backfill rule, and report section belong in
that vertical repository.

## Intelligence boundary

Each business repository supplies an `intelligence.json` taxonomy. The shared
package validates that registry, matches terms against already extracted
article facts, records bounded relations, and aggregates labels for a report.
It does not own company lists, source-specific semantics, raw text, or domain
conclusions. A label count means only that the reviewed articles matched the
configured vocabulary during the reporting window.
