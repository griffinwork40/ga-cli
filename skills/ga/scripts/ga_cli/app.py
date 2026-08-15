"""ga_cli — root Typer app, command registration, and centralized error wrap.

READ-ONLY GA4 CLI. All commands hit the API lazily, so `--help` works with no
credentials. Any GAError or google-api exception is rendered as
{"error": true, "message": "..."} JSON on stderr + exit 1.
"""

import json
import sys

import typer

app = typer.Typer(
    name="ga",
    help="Read-only Google Analytics 4 CLI (aggregate reports only). "
    "Set --property or GA_PROPERTY_ID to target a GA4 property. "
    "Run `ga properties` to discover accessible property IDs.",
    no_args_is_help=True,
    add_completion=False,
)

# Import command modules — triggers their @app.command() decorators.
from ga_cli import auth, report  # noqa: E402, F401


def main() -> None:
    """Entrypoint with centralized error handling.

    The app runs with ``standalone_mode=False`` so Click does not swallow
    exceptions or print its own traceback; every exit path terminates via a
    bare ``sys.exit(code)`` (which prints nothing). GAError and raw google-api
    exceptions (PermissionDenied, InvalidArgument, etc.) are normalized into
    the standard {"error": true, "message": "..."} JSON object on stderr so
    stdout stays clean and pipeable into jq — and stderr stays parseable too
    (no Python traceback trailing the JSON line).
    """
    # Typer (0.27) vendors Click under typer._click — there is no top-level
    # `click` in this venv. Import the exception classes from there.
    from typer._click import exceptions as click_exc

    from ga_cli.client import GAError

    try:
        # standalone_mode=False → Click returns/raises instead of sys.exit-ing
        # with a traceback. Normal completion returns the command's value.
        app(prog_name="ga", standalone_mode=False)
    except (click_exc.Exit, SystemExit) as e:
        # die() already printed the JSON error (or --help/no-args printed help).
        code = getattr(e, "exit_code", None)
        if code is None:
            code = getattr(e, "code", 0)
        sys.exit(code or 0)
    except click_exc.Abort:
        print(json.dumps({"error": True, "message": "Aborted."}), file=sys.stderr)
        sys.exit(1)
    except click_exc.ClickException as e:
        # Usage/parameter errors (e.g. missing --metrics). Keep Click's own
        # human-readable message but exit with its code (2).
        e.show()
        sys.exit(e.exit_code)
    except GAError as e:
        print(json.dumps({"error": True, "message": str(e)}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # google-api errors, network failures, etc.
        print(
            json.dumps({"error": True, "message": f"{type(e).__name__}: {e}"}),
            file=sys.stderr,
        )
        sys.exit(1)
