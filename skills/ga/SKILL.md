---
name: ga
allowed-tools: Bash, Read
description: >
  Read-only Google Analytics 4 CLI (`ga`) for pulling aggregate traffic data from
  any GA4 property the authorized Google account can see. Wraps the GA Admin API
  (property discovery) and Data API (runReport / getMetadata) behind Typer, with
  JSON-by-default output and a --pretty Rich renderer. Use this whenever you need
  to analyze GA4 traffic, acquisition channels, or source attribution; break down
  referrers / source-medium; find top pages/posts by views; see geo or daily session
  trends; or run an arbitrary metric×dimension GA4 report. Triggers: "analyze traffic",
  "where is traffic coming from", "acquisition channels", "top referrers",
  "top pages", "traffic trend", "GA4 report", "sessions/users last N days".
  READ-ONLY, aggregate-only (no user-level/PII). Requires GA OAuth (scope
  analytics.readonly) — see references/auth-setup.md.
---

# ga — read-only Google Analytics 4 CLI

## Overview

`ga` is a self-contained Python CLI (Typer + Rich) wrapping two Google Analytics 4
APIs, **read-only**:

- **Admin API** (`accountSummaries`) → `ga properties`
- **Data API** (`runReport`, `getMetadata`) → `ga report` + all canned reports

Every command prints **JSON to stdout by default** (pipe into `jq`); add `--pretty`
for a Rich table. Errors are emitted as `{"error": true, "message": "..."}` JSON on
**stderr** with **exit 1**, so stdout stays clean and pipeable even on failure.

**Auth:** user OAuth, scope `analytics.readonly` only. Cached token at
`~/.config/ga-cli/token.json`. `--help` works with no credentials — auth is only
touched when a command actually hits the API. See `references/auth-setup.md` (and
the **7-day token caveat** below).

**Property:** No default property ID is hardcoded. Set `--property <ID>` on any
command, or export `GA_PROPERTY_ID=<ID>`. Run `ga properties` to discover the
numeric IDs accessible to the authenticated account.

## Guardrails

- **Read-only.** Scope `analytics.readonly` only — no write/admin-write commands exist.
- **Aggregate-only.** Standard aggregate reports; no user-level / User-Explorer / PII exports.
- Never prints, cats, or logs the contents of `client_secret.json` or `token.json`.

## Command Reference

| Command | What it does |
|---|---|
| `ga properties` | List accessible properties (account + property names + numeric id) via Admin accountSummaries. |
| `ga auth [--reauth]` | Load/refresh creds from the cached token; `--reauth` forces fresh browser consent. Prints `authorized / token cached` status only. |
| `ga report --metrics …` | Generic runReport (any metrics × dimensions). See flags below. |
| `ga acquisition` | Sessions + users by `sessionDefaultChannelGroup`. |
| `ga referrers` | Sessions + users by `sessionSourceMedium`, top N. |
| `ga top-pages` | `screenPageViews` + sessions by `pagePath` (+`pageTitle`), top N. |
| `ga geo` | Sessions + users by `country`. |
| `ga trend` | Sessions + users by `date` (daily), ascending. |
| `ga metadata` | Dump all available dimensions & metrics for the property (getMetadata) as JSON. |

Canned reports (`acquisition`, `referrers`, `top-pages`, `geo`, `trend`) share:
`--days N` (trailing window), `--property <ID>`, `--limit N`, `--pretty`.

### `ga report` flags

| Flag | Default | Description |
|---|---|---|
| `--metrics m1,m2` | *(required)* | Comma-separated metrics, e.g. `sessions,totalUsers`. |
| `--dimensions d1,d2` | — | Comma-separated dimensions. |
| `--start` | `28daysAgo` | Start date (`YYYY-MM-DD` or `NdaysAgo`). |
| `--end` | `today` | End date (`YYYY-MM-DD` or `today`). |
| `--days N` | — | Convenience: sets `start=NdaysAgo` (overrides `--start`). |
| `--property <ID>` | `GA_PROPERTY_ID` env *(required if unset)* | Target property numeric ID. |
| `--limit N` | `100` | Max rows. |
| `--order-by field` | — | Order by a field; prefix `-` for descending (e.g. `-sessions`). |
| `--pretty` | off | Rich table instead of JSON. |

## Common workflows (copy-pasteable)

First, discover your property ID:

```bash
ga properties | jq -r '.rows[] | [.property_id, .account, .property] | @tsv'
```

Then set it once (or pass `--property` on each call):

```bash
export GA_PROPERTY_ID=<your-numeric-id>
```

### 1. Acquisition channels (last 28 days) — where traffic comes from

```bash
ga acquisition --days 28 --pretty

# Total sessions + users across all channels:
ga acquisition --days 28 \
  | jq '{sessions: ([.rows[].sessions|tonumber]|add), users: ([.rows[].totalUsers|tonumber]|add)}'
```

### 2. Top referrers (source / medium)

```bash
ga referrers --days 28 --limit 10 \
  | jq -r '.rows[] | [.sessions, .sessionSourceMedium] | @tsv'
```

### 3. Top pages / posts by views

```bash
ga top-pages --days 28 --limit 10 \
  | jq -r '.rows[] | [.screenPageViews, .pagePath] | @tsv'
```

### 4. Geo breakdown

```bash
ga geo --days 28 --limit 5 | jq -c '.rows[]'
```

### 5. Daily trend (last 14 days)

```bash
ga trend --days 14 | jq -r '.rows[] | [.date, .sessions, .totalUsers] | @tsv'
```

### 6. Arbitrary report — any metric × dimension

```bash
# Sessions + users by channel group, ordered desc, as a table:
ga report --metrics sessions,totalUsers \
  --dimensions sessionDefaultChannelGroup \
  --days 28 --order-by -sessions --pretty

# New vs returning users by device category over 90 days, JSON:
ga report --metrics activeUsers,newUsers \
  --dimensions deviceCategory --days 90 \
  | jq '.rows'

# Engagement rate + avg session duration, last 7 days:
ga report --metrics engagementRate,averageSessionDuration --days 7
```

### 7. Discover valid metrics/dimensions for a property

```bash
# What can I query?
ga metadata | jq '{dims: .dimension_count, metrics: .metric_count}'

# Search for a metric by name:
ga metadata | jq -r '.metrics[] | select(.api_name|test("user";"i")) | .api_name'

# Search dimensions:
ga metadata | jq -r '.dimensions[] | select(.api_name|test("source";"i")) | .api_name'
```

### 8. Query a different property inline

```bash
ga acquisition --property <other-id> --days 28
# or:
GA_PROPERTY_ID=<other-id> ga acquisition --days 28
```

## Output shape

`report` and every canned report return:

```json
{
  "property_id": "123456789",
  "date_range": {"start": "28daysAgo", "end": "today"},
  "dimensions": ["sessionDefaultChannelGroup"],
  "metrics": ["sessions", "totalUsers"],
  "row_count": 10,
  "rows": [
    {"sessionDefaultChannelGroup": "Organic Social", "sessions": "4921", "totalUsers": "4739"}
  ]
}
```

Rows are flat dicts (dimension columns + metric columns), so `jq '.rows[]'` and
`--pretty` tables Just Work. Metric values are **strings** (GA4 returns them as
strings) — use `tonumber` in `jq` before arithmetic.

## Error handling

- Any failure → `{"error": true, "message": "..."}` JSON on **stderr**, exit **1**.
  stdout stays empty/clean so pipelines don't ingest garbage.
- Invalid metric/dimension names → the message includes GA's "Did you mean …?" hint.
- `PermissionDenied (403)` → the account can't see that `--property`; check `ga properties`.
- Missing required flag (e.g. no `--metrics`) → Click usage error on stderr, exit **2**.
- No property set → clear message telling you to set `--property` or `GA_PROPERTY_ID`.
- Expired token → refresh-failed error telling you to run `ga auth --reauth`
  (see the 7-day caveat).

## ⚠️ 7-day token caveat (operational)

The OAuth consent screen is in **Testing** mode by default, so Google issues refresh
tokens that **expire ~7 days** after issue. Interactive use is fine (just re-consent),
but this **breaks unattended/daemon/scheduled runs** after a week. Fix before any
headless wiring: **publish the consent screen** (Testing → In production) *or* use a
**service account** (grant it Viewer on the property) for the scheduled leg. Details
in `references/auth-setup.md`.

## Layout

```
skills/ga/
├── SKILL.md
├── scripts/
│   ├── ga                      # bash entrypoint (SCRIPT_DIR-relative; chmod +x)
│   ├── requirements.txt        # pinned Python deps
│   └── ga_cli/
│       ├── __init__.py
│       ├── __main__.py         # `python -m ga_cli`
│       ├── app.py              # Typer root app + centralized error wrap
│       ├── client.py           # get_creds(), config/auth resolution,
│       │                       #   admin+data client factories, output helpers
│       ├── auth.py             # `ga auth`, `ga properties`
│       └── report.py           # generic `report` + canned reports
└── references/
    └── auth-setup.md           # GCP setup + the 7-day token caveat
```
