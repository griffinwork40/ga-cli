"""ga_cli -- data-stream discovery (`ga datastreams`)."""

from typing import Optional

import typer

from ga_cli.app import app
from ga_cli.client import admin_client, emit, get_creds, resolve_property


@app.command()
def datastreams(
    property_id: Optional[str] = typer.Option(
        None, "--property", help="GA4 property ID (overrides GA_PROPERTY_ID env)."
    ),
    pretty: bool = False,
):
    """List data streams for a property (measurement ID, URI, display name).

    Shows every web, iOS, and Android data stream attached to the property.
    For web streams the measurement ID (G-XXXXXXXXXX) is included -- this is
    the value you set in NEXT_PUBLIC_GA_MEASUREMENT_ID or equivalent.

    Read-only. Uses the Admin API listDataStreams endpoint.
    """
    pid = resolve_property(property_id)
    creds = get_creds()
    client = admin_client(creds)
    rows = []
    for stream in client.list_data_streams(parent=f"properties/{pid}"):
        row = {
            "display_name": stream.display_name,
            "stream_id": stream.name.split("/")[-1],
            "type": str(stream.type_).replace("DataStreamType.", ""),
        }
        if stream.web_stream_data:
            row["measurement_id"] = stream.web_stream_data.measurement_id
            row["default_uri"] = stream.web_stream_data.default_uri
        if stream.ios_app_stream_data:
            row["bundle_id"] = stream.ios_app_stream_data.bundle_id
        if stream.android_app_stream_data:
            row["package_name"] = stream.android_app_stream_data.package_name
        rows.append(row)
    emit(
        {"property_id": pid, "rows": rows, "count": len(rows)},
        pretty,
        table_title=f"Data Streams (property {pid})",
    )
