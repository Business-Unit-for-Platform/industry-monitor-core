# Industry Monitor Core Architecture

`industry-monitor-core` is the shared platform foundation for business-unit
industry monitors. It is intentionally domain-neutral and public.

## Ownership

### Core package

- Safe HTTP collection: robots, TLS, reviewed-host allowlists, redirects,
  request spacing, response-size limits, and challenge-page rejection.
- URL normalization, date parsing, text cleanup, hashing, excerpts, and
  Markdown escaping.
- Generic page model, reviewed article-link discovery, bounded body extraction,
  attachment-link registration, and external-candidate registration.
- Domain-neutral AKShare ETF normalization, registry validation, snapshot
  orchestration, and public-field allowlists.

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
industry_monitor_core.web + industry_monitor_core.akshare_etf
          |
          v
domain archive -> domain report -> domain publication / notification
```

The core package never imports a business repository and never reads a source
registry, a credential, or a domain data directory. A third business unit
should add configuration or a small domain adapter rather than copying a
business repository's data or report code.

## Migration rule

Migration is incremental. A business repository may first install a pinned
core commit and use a compatibility import while its existing tests remain
green. The duplicate implementation is deleted only after integration tests
prove that URL, robots, extraction, archive, and public-report behavior is
unchanged.

The compatibility period is an intentional SRP/DRY trade-off to preserve the
current production path while the shared API is validated.
