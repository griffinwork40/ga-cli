# ga-cli

CLI for the Google Analytics 4 Data API — pull aggregate traffic reports from any GA4 property. Read-only, aggregate-only (no PII). An [AFK](https://github.com/griffinwork40/agent-afk) plugin.

Wraps the GA Admin API (property discovery) and Data API (runReport / getMetadata) behind a Typer CLI. JSON by default (pipe into `jq`); `--pretty` for Rich tables. No hardcoded property — works with any GA4 property the authenticated Google account can see.

## Install

### As an AFK plugin (recommended)

```bash
afk plugin install griffinwork40/ga-cli
```

This registers the `ga` skill, available in every AFK session. Install the Python dependencies once from the bundled requirements file:

```bash
pip install -r ~/.afk/plugins/ga-cli/skills/ga/scripts/requirements.txt
```

### As a standalone CLI

Requires Python 3.11+.

```bash
git clone https://github.com/griffinwork40/ga-cli.git
cd ga-cli/skills/ga/scripts
pip install -r requirements.txt

# Optional: put `ga` on your PATH
ln -s "$(pwd)/ga" /usr/local/bin/ga
ga --help
```

## Features

- **Read-only:** scope `analytics.readonly` only — no write operations.
- **Aggregate-only:** standard GA4 reports; no user-level / User-Explorer / PII.
- **Property discovery:** `ga properties` lists every GA4 property the authenticated account can see, with numeric IDs for use with `--property`.
- **Canned reports:** acquisition channels, referrers (source/medium), top pages, geo breakdown, daily trend.
- **Generic report:** `ga report --metrics … --dimensions …` runs any runReport query.
- **Metadata:** `ga metadata` dumps all available dimensions and metrics for a property.
- **Machine-friendly:** compact JSON to stdout by default; errors are JSON on stderr with a nonzero exit code; stdout stays clean and pipeable even on failure.
- **`--pretty`** renders a Rich table for any command.

## Authentication

`ga` uses user OAuth (a Desktop OAuth client), read-only scope only. Full setup walkthrough: [`skills/ga/references/auth-setup.md`](skills/ga/references/auth-setup.md).

In short:

1. In [Google Cloud Console](https://console.cloud.google.com/), enable **both** the Google Analytics Admin API and the Google Analytics Data API.
2. Create an OAuth client (Desktop app), download the JSON, and save it to:
   ```
   ~/.config/ga-cli/client_secret.json
   ```
3. Run the first-time consent flow:
   ```bash
   ga auth --reauth
   ```
   A browser window opens. On the "Google hasn't verified this app" screen: **Advanced → Go to \<app\> (unsafe) → allow read-only Analytics.**
4. The refresh token is cached at `~/.config/ga-cli/token.json` (chmod 0600). Subsequent commands refresh silently.

**Token paths and overrides:**

| Purpose | Default | Env override |
|---|---|---|
| OAuth client secret | `~/.config/ga-cli/client_secret.json` | `GA_CLIENT_SECRET` |
| Cached refresh token | `~/.config/ga-cli/token.json` | `GA_TOKEN` |

> ⚠️ **Testing-mode tokens expire in ~7 days.** If you plan to run `ga` in a scheduled/headless context, either publish the OAuth consent screen (Testing → In production) or switch to a service account. See [`auth-setup.md`](skills/ga/references/auth-setup.md) for details.

## Command reference

```
ga properties               List accessible GA4 properties (account + property name + numeric ID)
ga auth [--reauth]          Load/refresh OAuth creds; --reauth forces fresh browser consent
ga report --metrics …       Generic runReport (any metrics × dimensions)
ga acquisition              Sessions + users by default channel group
ga referrers                Sessions + users by source / medium (top referrers)
ga top-pages                Page views + sessions by page path + title, top N
ga geo                      Sessions + users by country
ga trend                    Sessions + users by date (daily), ascending
ga metadata                 Dump all dimensions & metrics for the property
```

All commands accept `--property <ID>` (or set `GA_PROPERTY_ID` in the environment). Run `ga properties` to find the numeric ID for your property. All commands support `--pretty` for a Rich table.

### Setting your property

No property ID is hardcoded. Before running data commands:

```bash
# Discover your property IDs:
ga properties | jq -r '.rows[] | [.property_id, .account, .property] | @tsv'

# Set for the session:
export GA_PROPERTY_ID=123456789

# Or pass per-command:
ga acquisition --property 123456789 --days 28
```

### Common workflows

```bash
# Acquisition channels — where traffic comes from:
ga acquisition --days 28 --pretty

# Total sessions + users across all channels:
ga acquisition --days 28 \
  | jq '{sessions: ([.rows[].sessions|tonumber]|add), users: ([.rows[].totalUsers|tonumber]|add)}'

# Top referrers (source / medium):
ga referrers --days 28 --limit 10 \
  | jq -r '.rows[] | [.sessions, .sessionSourceMedium] | @tsv'

# Top pages by view count:
ga top-pages --days 28 --limit 10 \
  | jq -r '.rows[] | [.screenPageViews, .pagePath] | @tsv'

# Daily trend, last 14 days:
ga trend --days 14 | jq -r '.rows[] | [.date, .sessions, .totalUsers] | @tsv'

# Arbitrary report — any metric × dimension:
ga report --metrics sessions,totalUsers \
  --dimensions sessionDefaultChannelGroup \
  --days 28 --order-by -sessions --pretty

# Discover available metrics + dimensions:
ga metadata | jq '{dims: .dimension_count, metrics: .metric_count}'
ga metadata | jq -r '.metrics[] | select(.api_name|test("user";"i")) | .api_name'
```

### Output shape

```json
{
  "property_id": "123456789",
  "date_range": {"start": "28daysAgo", "end": "today"},
  "dimensions": ["sessionDefaultChannelGroup"],
  "metrics": ["sessions", "totalUsers"],
  "row_count": 8,
  "rows": [
    {"sessionDefaultChannelGroup": "Organic Social", "sessions": "4921", "totalUsers": "4739"}
  ]
}
```

Metric values are **strings** (GA4 API returns them as strings) — use `tonumber` in `jq` before arithmetic.

## Repository layout

```
ga-cli/
├── .claude-plugin/plugin.json        # AFK plugin manifest
├── skills/ga/
│   ├── SKILL.md                      # skill manifest (agent-facing usage)
│   ├── scripts/
│   │   ├── ga                        # bash entrypoint (SCRIPT_DIR-relative)
│   │   ├── requirements.txt          # pinned Python deps
│   │   └── ga_cli/                   # Python package
│   │       ├── __init__.py
│   │       ├── __main__.py
│   │       ├── app.py                # Typer root + error handling
│   │       ├── client.py             # auth, property resolution, output helpers
│   │       ├── auth.py               # `ga auth`, `ga properties`
│   │       └── report.py             # `ga report` + canned reports
│   └── references/
│       └── auth-setup.md             # GCP OAuth setup + 7-day token caveat
├── README.md
└── LICENSE
```

## License

[MIT](LICENSE) © 2026 Griffin Long
