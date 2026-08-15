"""ga_cli — auth + property discovery commands (`ga auth`, `ga properties`)."""

from ga_cli.app import app
from ga_cli.client import admin_client, emit, get_creds


@app.command()
def auth(
    reauth: bool = False,
):
    """Load/refresh OAuth creds using the cached token.

    --reauth forces a fresh browser consent. Prints an authorized/token-cached
    status object only — never the token contents.
    """
    creds = get_creds(reauth=reauth)
    emit(
        {
            "status": "authorized",
            "token": "cached",
            "scopes": list(getattr(creds, "scopes", []) or []),
            "valid": bool(getattr(creds, "valid", False)),
        },
        pretty=False,
        table_title="Auth",
    )


@app.command()
def properties(
    pretty: bool = False,
):
    """List accessible GA4 properties (account + property names + numeric id).

    Uses the Admin API accountSummaries endpoint. Read-only.
    """
    creds = get_creds()
    client = admin_client(creds)
    rows = []
    for acct in client.list_account_summaries():
        for prop in acct.property_summaries:
            rows.append(
                {
                    "account": acct.display_name,
                    "property": prop.display_name,
                    "property_id": prop.property.split("/")[-1],
                }
            )
    emit({"rows": rows, "count": len(rows)}, pretty, table_title="Properties")
