"""Project/session state for GeoServer CLI."""

import json
import time


def create_session(url="http://localhost:8080/geoserver", username="admin", password="geoserver", workspace=None):
    """Create a new CLI session state."""
    return {
        "version": "1.0.0",
        "url": url,
        "username": username,
        "password": password,
        "workspace": workspace,
        "created": time.time(),
        "modified": time.time(),
        "history": [],
    }


def save_session(session, path):
    """Save session state to JSON file."""
    session["modified"] = time.time()
    with open(path, "w") as f:
        json.dump(session, f, indent=2)
    return path


def load_session(path):
    """Load session state from JSON file."""
    with open(path) as f:
        return json.load(f)


def session_info(session):
    """Get human-readable session info."""
    return {
        "url": session.get("url", ""),
        "username": session.get("username", ""),
        "workspace": session.get("workspace", "(none)"),
        "created": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(session.get("created", 0))),
        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(session.get("modified", 0))),
        "history_length": len(session.get("history", [])),
    }


def add_history(session, command):
    """Add a command to session history."""
    session.setdefault("history", []).append(
        {
            "command": command,
            "timestamp": time.time(),
        }
    )
    session["modified"] = time.time()
