#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fulcra-api==0.1.28",
# ]
# ///
"""Fulcra personal context CLI.

- Exactly one JSON object is printed to stdout on success.
- Diagnostics/errors are printed to stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

AUTH_PATH = Path.home() / ".config" / "fulcra-agent" / "auth.json"


class FulcraAgentError(RuntimeError):
    """Expected operational errors for CLI-friendly handling."""


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def to_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "to_dict"):
        return value.to_dict()  # pandas DataFrame/Series friendly
    if hasattr(value, "tolist"):
        return value.tolist()
    return str(value)


def write_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, default=to_json, separators=(",", ":")))


def now_utc() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def ensure_auth_dir() -> None:
    AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_auth() -> dict[str, Any] | None:
    if not AUTH_PATH.exists():
        return None
    try:
        data = json.loads(AUTH_PATH.read_text())
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_auth(auth: dict[str, Any]) -> None:
    ensure_auth_dir()
    AUTH_PATH.write_text(json.dumps(auth, indent=2, sort_keys=True))


def clear_auth() -> None:
    AUTH_PATH.unlink(missing_ok=True)


def import_fulcra_api() -> Any:
    try:
        from fulcra_api.core import FulcraAPI  # type: ignore
    except ImportError as exc:
        raise FulcraAgentError(
            "Missing dependency `fulcra-api==0.1.28`. Run with `uv run fulcra_agent.py ...`."
        ) from exc
    return FulcraAPI


def build_client(auth: dict[str, Any] | None) -> Any:
    FulcraAPI = import_fulcra_api()
    kwargs: dict[str, Any] = {}
    if auth:
        token = auth.get("access_token")
        if isinstance(token, str) and token:
            kwargs["access_token"] = token

        expiration = parse_iso8601(auth.get("access_token_expiration"))
        if expiration:
            kwargs["access_token_expiration"] = expiration

        refresh = auth.get("refresh_token")
        if isinstance(refresh, str) and refresh:
            kwargs["refresh_token"] = refresh

    return FulcraAPI(**kwargs)


def extract_auth(client: Any) -> dict[str, Any]:
    exp = getattr(client, "fulcra_cached_access_token_expiration", None)
    return {
        "access_token": getattr(client, "fulcra_cached_access_token", None),
        "access_token_expiration": exp.isoformat() if isinstance(exp, datetime) else None,
        "refresh_token": getattr(client, "fulcra_cached_refresh_token", None),
        "authorized_at": iso(now_utc()),
    }


def ensure_authenticated(client: Any, attempt_login: bool = False) -> None:
    token = getattr(client, "fulcra_cached_access_token", None)
    exp = getattr(client, "fulcra_cached_access_token_expiration", None)

    if token and isinstance(exp, datetime) and exp > now_utc():
        return

    if token and isinstance(exp, datetime) and exp <= now_utc():
        refresh_token = getattr(client, "fulcra_cached_refresh_token", None)
        if refresh_token:
            try:
                if client.refresh_access_token():
                    return
            except Exception:
                pass

    if attempt_login:
        client.authorize()
        token = getattr(client, "fulcra_cached_access_token", None)
        if token:
            return

    raise FulcraAgentError(
        "Not authenticated. Run `auth login` first (or re-run if your token expired)."
    )


def resolve_user_timezone(user_info: dict[str, Any] | None) -> str:
    if not isinstance(user_info, dict):
        return "UTC"

    top_level = user_info.get("timezone")
    if isinstance(top_level, str) and top_level:
        return top_level

    prefs = user_info.get("preferences")
    if isinstance(prefs, dict):
        tz = prefs.get("timezone")
        if isinstance(tz, str) and tz:
            return tz

    return "UTC"


def pick_latest_completed_sleep(cycles: Any, now: datetime) -> dict[str, Any] | None:
    if cycles is None:
        return None

    if hasattr(cycles, "to_dict"):
        rows = cycles.to_dict(orient="records")
    elif isinstance(cycles, list):
        rows = cycles
    else:
        return None

    completed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        end_time = (
            row.get("end_time")
            or row.get("end")
            or row.get("cycle_end")
            or row.get("ended_at")
        )
        if isinstance(end_time, str):
            end_dt = parse_iso8601(end_time)
            if end_dt and end_dt <= now:
                completed.append(row)

    if not completed:
        return None

    def end_sort_key(item: dict[str, Any]) -> datetime:
        return parse_iso8601(
            item.get("end_time") or item.get("end") or item.get("cycle_end") or item.get("ended_at")
        ) or datetime.min.replace(tzinfo=UTC)

    return sorted(completed, key=end_sort_key)[-1]


def command_auth_login(_: argparse.Namespace) -> None:
    client = build_client(load_auth())
    client.authorize()
    auth = extract_auth(client)
    if not auth.get("access_token"):
        raise FulcraAgentError("Authorization did not return an access token.")
    save_auth(auth)
    write_json(
        {
            "ok": True,
            "command": "auth login",
            "auth_path": str(AUTH_PATH),
            "authorized_at": auth["authorized_at"],
            "has_refresh_token": bool(auth.get("refresh_token")),
        }
    )


def command_auth_status(_: argparse.Namespace) -> None:
    auth = load_auth()
    authenticated = False
    expires_at = None

    if auth:
        expires_at = auth.get("access_token_expiration")
        token = auth.get("access_token")
        exp = parse_iso8601(expires_at)
        authenticated = bool(token and exp and exp > now_utc())

    write_json(
        {
            "ok": True,
            "command": "auth status",
            "auth_path": str(AUTH_PATH),
            "auth_file_present": bool(auth),
            "authenticated": authenticated,
            "access_token_expiration": expires_at,
            "authorized_at": auth.get("authorized_at") if auth else None,
        }
    )


def command_auth_logout(_: argparse.Namespace) -> None:
    clear_auth()
    write_json(
        {
            "ok": True,
            "command": "auth logout",
            "auth_path": str(AUTH_PATH),
            "authenticated": False,
        }
    )


def command_bootstrap(_: argparse.Namespace) -> None:
    client = build_client(load_auth())
    ensure_authenticated(client)

    user_info = client.get_user_info()
    calendars = client.calendars()
    metrics = client.metrics_catalog()

    write_json(
        {
            "ok": True,
            "command": "bootstrap",
            "generated_at": iso(now_utc()),
            "user_info": user_info,
            "calendars": calendars,
            "metrics_catalog": metrics,
        }
    )


def command_sleep(_: argparse.Namespace) -> None:
    client = build_client(load_auth())
    ensure_authenticated(client)

    end = now_utc()
    start = end - timedelta(hours=48)
    cycles = client.sleep_cycles(start, end)
    latest = pick_latest_completed_sleep(cycles, end)

    write_json(
        {
            "ok": True,
            "command": "sleep",
            "generated_at": iso(end),
            "window": {"start": iso(start), "end": iso(end)},
            "latest_completed_sleep": latest,
            "sleep_cycles": cycles,
        }
    )


def command_visits(_: argparse.Namespace) -> None:
    client = build_client(load_auth())
    ensure_authenticated(client)

    end = now_utc()
    start = end - timedelta(hours=24)

    visits = client.apple_location_visits(start, end)
    updates = client.apple_location_updates(start, end)

    write_json(
        {
            "ok": True,
            "command": "visits",
            "generated_at": iso(end),
            "window": {"start": iso(start), "end": iso(end)},
            "visits": visits,
            "location_updates": updates,
        }
    )


def command_workouts(_: argparse.Namespace) -> None:
    client = build_client(load_auth())
    ensure_authenticated(client)

    end = now_utc()
    start = end - timedelta(days=7)
    workouts = client.apple_workouts(start, end)

    write_json(
        {
            "ok": True,
            "command": "workouts",
            "generated_at": iso(end),
            "window": {"start": iso(start), "end": iso(end)},
            "workouts": workouts,
        }
    )


def command_checkin(_: argparse.Namespace) -> None:
    client = build_client(load_auth())
    ensure_authenticated(client)

    generated_at = now_utc()
    start = generated_at - timedelta(hours=24)

    user_info = client.get_user_info()
    timezone_name = resolve_user_timezone(user_info)
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        timezone_name = "UTC"
        tz = ZoneInfo("UTC")

    visits = client.apple_location_visits(start, generated_at)
    workouts = client.apple_workouts(start, generated_at)
    sleep_cycles = client.sleep_cycles(start - timedelta(hours=24), generated_at)
    latest_sleep = pick_latest_completed_sleep(sleep_cycles, generated_at)

    local_now = generated_at.astimezone(tz)
    local_next_12h = local_now + timedelta(hours=12)
    next_events = client.calendar_events(local_now, local_next_12h)

    current_location = client.location_at_time(generated_at, reverse_geocode=True)

    write_json(
        {
            "ok": True,
            "command": "checkin",
            "generated_at": iso(generated_at),
            "timezone": timezone_name,
            "window": {"start": iso(start), "end": iso(generated_at)},
            "current_location": current_location,
            "visits": visits,
            "latest_completed_sleep": latest_sleep,
            "workouts": workouts,
            "next_event": next_events[0] if next_events else None,
            "next_events": next_events,
            "user_info": user_info,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fulcra_agent.py",
        description="Fulcra personal context CLI with deterministic JSON output.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    auth_parser = sub.add_parser("auth", help="Authentication commands")
    auth_sub = auth_parser.add_subparsers(dest="auth_command", required=True)

    login = auth_sub.add_parser("login", help="Run Fulcra device auth flow")
    login.set_defaults(func=command_auth_login)

    status = auth_sub.add_parser("status", help="Show persisted auth status")
    status.set_defaults(func=command_auth_status)

    logout = auth_sub.add_parser("logout", help="Clear persisted auth")
    logout.set_defaults(func=command_auth_logout)

    bootstrap = sub.add_parser("bootstrap", help="Load user info, calendars, metrics")
    bootstrap.set_defaults(func=command_bootstrap)

    sleep = sub.add_parser("sleep", help="Return latest completed sleep cycle")
    sleep.set_defaults(func=command_sleep)

    visits = sub.add_parser("visits", help="Return visits and location updates (24h)")
    visits.set_defaults(func=command_visits)

    workouts = sub.add_parser("workouts", help="Return workouts (7d)")
    workouts.set_defaults(func=command_workouts)

    checkin = sub.add_parser("checkin", help="Return compact 24h personal context summary")
    checkin.set_defaults(func=command_checkin)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        args.func(args)
        return 0
    except FulcraAgentError as exc:
        eprint(f"error: {exc}")
        return 2
    except Exception as exc:
        eprint(f"unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
