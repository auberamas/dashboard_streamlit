"""The local version of the raw file, kept in a small json file.

Only one thing really matters here: the last_modified date that data.gouv.fr announced the day
the local copy was downloaded
Everything is stored in UTC to avoid timezone shifts or daylight saving time changes
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from utils.config import DATA_DIR

STATE_FILE = DATA_DIR / "state.json"

EMPTY = {
    "remote_last_modified": None,  # what data.gouv announced for the local copy
    "downloaded_at": None,  # when the local copy was written
    "size_bytes": None,
    "resource_id": None,
}


def read_state(path=None):
    """Current state, or an empty one when the file does not exist or is unreadable

    The path is read at call time and not frozen at import so a test or another deployment
    can point the module somewhere else
    """
    path = Path(path or STATE_FILE)
    if not path.exists():
        return dict(EMPTY)
    try:
        stored = json.loads(path.read_text(encoding="utf-8")) # get data\state.json
    except (json.JSONDecodeError, OSError):
        return dict(EMPTY)
    state = dict(EMPTY)
    state.update({key: stored.get(key) for key in EMPTY})
    return state


def write_state(state, path=None):
    """Write the state through a temporary file so it is never left half written"""
    path = Path(path or STATE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)
    return state


def parse_date(value):
    """Read a date coming from data.gouv or from the state file. None when it cannot be read"""
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    # a date without a time zone is read as utc so two dates are always comparable
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def now_utc():
    """Current time in utc as text"""
    return datetime.now(timezone.utc).isoformat()


def is_outdated(local_value, remote_value):
    """True when the remote file is newer than the local copy.

    An unknown remote date means nothing can be compared so the local copy is kept.
    """
    remote = parse_date(remote_value)
    local = parse_date(local_value)
    if remote is None:
        return False
    if local is None:
        return True
    return remote > local
