"""ga_cli — auth, config resolution, client factories, output + error helpers.

READ-ONLY. Scope analytics.readonly ONLY. get_creds() uses the standard
InstalledAppFlow / token-refresh pattern for Desktop OAuth clients.

Auth is LAZY: importing this module or building a Typer command must NOT touch
the token. Credentials are only loaded when a command actually hits the API
(via get_creds / admin_client / data_client), so `--help` works with no creds.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG = Path.home() / ".config" / "ga-cli"
CLIENT_SECRET = CONFIG / "client_secret.json"
TOKEN = CONFIG / "token.json"
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

# No hardcoded default property — users must set GA_PROPERTY_ID or --property.
# Run `ga properties` to discover accessible property IDs.
DEFAULT_PROPERTY_ID = None

console = Console()  # Rich console for --pretty tables (stdout)
err_console = Console(stderr=True)  # human-readable diagnostics to stderr


# ---------------------------------------------------------------------------
# Error handling — errors surface as {"error": true, "message": "..."} JSON on
# stderr + exit 1 (mirrors the hunter-io convention). CLI JSON on stdout stays
# clean and pipeable into jq even when a call fails.
# ---------------------------------------------------------------------------


class GAError(Exception):
    """Raised for any user-facing failure; caught centrally in app.main()."""


def die(message: str) -> "typer.Exit":
    """Emit a JSON error object on stderr and exit 1."""
    print(json.dumps({"error": True, "message": message}), file=sys.stderr)
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Auth — resolution priority: GA_CLIENT_SECRET / GA_TOKEN env vars override the
# config-file paths (env var -> config-file fallback, mirroring threads-api).
# ---------------------------------------------------------------------------


def _client_secret_path() -> Path:
    return Path(os.environ.get("GA_CLIENT_SECRET", str(CLIENT_SECRET)))


def _token_path() -> Path:
    return Path(os.environ.get("GA_TOKEN", str(TOKEN)))


def get_creds(reauth: bool = False):
    """Load/refresh cached creds; run browser consent only if needed.

    Resolution priority: GA_CLIENT_SECRET / GA_TOKEN env vars override the
    default config-file paths. The `reauth` flag forces fresh browser consent.
    Raises GAError (never a bare exception) so failures render as the standard
    JSON error object. Never prints or returns token/secret contents.
    """
    # Import lazily so `--help` and arg parsing never require google libs to
    # resolve credentials.
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = _token_path()
    secret_path = _client_secret_path()

    creds = None
    if token_path.exists() and not reauth:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if reauth or not creds or not creds.valid:
        if not reauth and creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:  # refresh token expired/revoked
                raise GAError(
                    f"Token refresh failed ({type(e).__name__}). "
                    "Re-run `ga auth --reauth` to grant fresh consent. "
                    "Note: consent screens in Testing mode expire refresh "
                    "tokens ~7 days (see references/auth-setup.md)."
                )
        else:
            if not secret_path.exists():
                raise GAError(
                    f"No client secret at {secret_path}. See "
                    "references/auth-setup.md to create a Desktop OAuth client."
                )
            # Interactive browser consent — only path that opens a browser.
            err_console.print(
                ">>> A browser window is opening. Approve access with the "
                "Google account that has GA access.\n"
                ">>> You'll hit a 'Google hasn't verified this app' screen "
                "(normal in Testing mode): click 'Advanced' -> 'Go to <app> "
                "(unsafe)' -> allow read-only Analytics."
            )
            flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
            creds = flow.run_local_server(port=0, prompt="consent")
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        os.chmod(token_path, 0o600)
    return creds


# ---------------------------------------------------------------------------
# Client factories — lazy imports keep `--help` credential-free.
# ---------------------------------------------------------------------------


def admin_client(creds):
    from google.analytics.admin_v1beta import AnalyticsAdminServiceClient

    return AnalyticsAdminServiceClient(credentials=creds)


def data_client(creds):
    from google.analytics.data_v1beta import BetaAnalyticsDataClient

    return BetaAnalyticsDataClient(credentials=creds)


# ---------------------------------------------------------------------------
# Property resolution — explicit --property > GA_PROPERTY_ID env > error.
# ---------------------------------------------------------------------------


def resolve_property(property_id: Optional[str]) -> str:
    pid = property_id or os.environ.get("GA_PROPERTY_ID") or DEFAULT_PROPERTY_ID
    if not pid:
        raise GAError(
            "No GA4 property specified. Set --property <ID> or export "
            "GA_PROPERTY_ID=<ID>. Run `ga properties` to list accessible "
            "property IDs."
        )
    # Accept either "123456789" or "properties/123456789"; normalize to numeric.
    return str(pid).split("/")[-1]


# ---------------------------------------------------------------------------
# Output helpers — JSON on stdout by default; Rich table on --pretty.
# ---------------------------------------------------------------------------


def emit(data, pretty: bool, *, table_title: str = "Result") -> None:
    """Print a dict/list. JSON to stdout by default; Rich rendering if pretty."""
    if not pretty:
        print(json.dumps(data))
        return
    # Pretty: render a list of flat dicts as a table; otherwise pretty JSON.
    rows = data.get("rows") if isinstance(data, dict) else data
    if isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows):
        table = Table(title=table_title, show_header=True, header_style="bold cyan")
        cols = list(rows[0].keys())
        for c in cols:
            table.add_column(str(c))
        for r in rows:
            table.add_row(*[str(r.get(c, "")) for c in cols])
        console.print(table)
    else:
        from rich.panel import Panel

        console.print(
            Panel.fit(
                json.dumps(data, indent=2),
                title=f"[bold green]{table_title}[/bold green]",
            )
        )
