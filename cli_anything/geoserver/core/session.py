"""Stateful session management with undo/redo for GeoServer CLI."""

import copy
import json
import time


class Session:
    """Manages stateful CLI session with connection context and undo/redo."""

    def __init__(self, url="http://localhost:8080/geoserver", username="admin",
                 password="geoserver"):
        self.url = url
        self.username = username
        self.password = password
        self.workspace = None
        self.history = []
        self.undo_stack = []
        self.redo_stack = []
        self.created = time.time()
        self.modified = time.time()

    def set_workspace(self, workspace):
        """Set current workspace context."""
        old = self.workspace
        self.workspace = workspace
        self._record("set_workspace", {"old": old, "new": workspace})

    def record_action(self, action, params, result=None):
        """Record an action in history."""
        entry = {
            "action": action,
            "params": params,
            "result": result,
            "timestamp": time.time(),
        }
        self.history.append(entry)
        self.modified = time.time()

    def _record(self, action, data):
        self.undo_stack.append({"action": action, "data": data})
        self.redo_stack.clear()

    def to_dict(self):
        """Serialize session to dict."""
        return {
            "url": self.url,
            "username": self.username,
            "password": self.password,
            "workspace": self.workspace,
            "history": self.history,
            "created": self.created,
            "modified": self.modified,
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize session from dict."""
        s = cls(
            url=data.get("url", "http://localhost:8080/geoserver"),
            username=data.get("username", "admin"),
            password=data.get("password", "geoserver"),
        )
        s.workspace = data.get("workspace")
        s.history = data.get("history", [])
        s.created = data.get("created", time.time())
        s.modified = data.get("modified", time.time())
        return s

    def save(self, path):
        """Save session to file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path):
        """Load session from file."""
        with open(path, "r") as f:
            return cls.from_dict(json.load(f))

    def status(self):
        """Get session status dict."""
        return {
            "url": self.url,
            "username": self.username,
            "workspace": self.workspace or "(none)",
            "actions": len(self.history),
            "undo_available": len(self.undo_stack),
        }
