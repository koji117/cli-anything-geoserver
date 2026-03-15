"""Unit tests for cli-anything-geoserver — synthetic data, no GeoServer required."""

import json
import os
import sys
import subprocess
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from cli_anything.geoserver.core.session import Session
from cli_anything.geoserver.core.project import (
    create_session, save_session, load_session, session_info, add_history,
)
from cli_anything.geoserver.utils.geoserver_backend import (
    GeoServerClient, GeoServerError,
)
from cli_anything.geoserver.geoserver_cli import cli


# ── Session (core/session.py) ────────────────────────────────────────────

class TestSession:
    def test_create_default(self):
        s = Session()
        assert s.url == "http://localhost:8080/geoserver"
        assert s.username == "admin"
        assert s.password == "geoserver"
        assert s.workspace is None
        assert s.history == []

    def test_create_custom(self):
        s = Session(url="http://myserver:9090/gs", username="user1", password="pass1")
        assert s.url == "http://myserver:9090/gs"
        assert s.username == "user1"
        assert s.password == "pass1"

    def test_set_workspace(self):
        s = Session()
        s.set_workspace("topp")
        assert s.workspace == "topp"
        assert len(s.undo_stack) == 1

    def test_record_action(self):
        s = Session()
        s.record_action("list_workspaces", {}, result=["ws1", "ws2"])
        assert len(s.history) == 1
        assert s.history[0]["action"] == "list_workspaces"

    def test_to_dict_and_from_dict(self):
        s = Session(url="http://test:8080/gs", username="u", password="p")
        s.set_workspace("myws")
        s.record_action("test", {"key": "val"})
        d = s.to_dict()
        s2 = Session.from_dict(d)
        assert s2.url == "http://test:8080/gs"
        assert s2.workspace == "myws"
        assert len(s2.history) == 1

    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            s = Session()
            s.set_workspace("test_ws")
            s.save(path)
            s2 = Session.load(path)
            assert s2.workspace == "test_ws"
        finally:
            os.unlink(path)

    def test_status(self):
        s = Session()
        s.set_workspace("demo")
        status = s.status()
        assert status["workspace"] == "demo"
        assert status["url"] == "http://localhost:8080/geoserver"
        assert "actions" in status


# ── Project (core/project.py) ────────────────────────────────────────────

class TestProject:
    def test_create_session(self):
        sess = create_session()
        assert sess["url"] == "http://localhost:8080/geoserver"
        assert sess["username"] == "admin"
        assert sess["workspace"] is None
        assert "created" in sess

    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            sess = create_session(workspace="test")
            save_session(sess, path)
            loaded = load_session(path)
            assert loaded["workspace"] == "test"
        finally:
            os.unlink(path)

    def test_session_info(self):
        sess = create_session(workspace="demo")
        info = session_info(sess)
        assert info["workspace"] == "demo"
        assert info["username"] == "admin"

    def test_add_history(self):
        sess = create_session()
        add_history(sess, "workspace list")
        add_history(sess, "layer list")
        assert len(sess["history"]) == 2
        assert sess["history"][0]["command"] == "workspace list"


# ── GeoServerClient (utils/geoserver_backend.py) ─────────────────────────

class TestGeoServerClient:
    def test_url_construction(self):
        client = GeoServerClient(url="http://myhost:9090/geoserver")
        assert client.rest_url == "http://myhost:9090/geoserver/rest"
        assert client._url("workspaces") == "http://myhost:9090/geoserver/rest/workspaces"
        assert client._url("/workspaces") == "http://myhost:9090/geoserver/rest/workspaces"

    def test_connection_error(self):
        client = GeoServerClient(url="http://localhost:19999/nonexistent")
        with pytest.raises(GeoServerError, match="Cannot connect"):
            client.list_workspaces()

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_api_error_propagation(self, mock_req):
        mock_req.side_effect = GeoServerError("Not Found", status_code=404)
        client = GeoServerClient()
        with pytest.raises(GeoServerError) as exc_info:
            client.get_workspace("nonexistent")
        assert exc_info.value.status_code == 404

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_list_workspaces_empty(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"workspaces": ""}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.list_workspaces()
        assert result == []


# ── Export (core/export.py) ──────────────────────────────────────────────

class TestExport:
    @patch("cli_anything.geoserver.core.export.GeoServerClient")
    def test_export_map(self, MockClient):
        from cli_anything.geoserver.core.export import export_map
        mock_client = MagicMock()
        # Return fake PNG data (PNG magic bytes)
        mock_client.wms_getmap.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "test.png")
            result = export_map(mock_client, "test:layer", out, bbox="-180,-90,180,90")
            assert os.path.exists(out)
            assert result["file_size"] > 0
            assert result["layers"] == "test:layer"
            with open(out, "rb") as f:
                assert f.read(4) == b"\x89PNG"

    @patch("cli_anything.geoserver.core.export.GeoServerClient")
    def test_export_features(self, MockClient):
        from cli_anything.geoserver.core.export import export_features
        mock_client = MagicMock()
        mock_client.wfs_getfeature.return_value = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": None, "properties": {"id": 1}}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "test.geojson")
            result = export_features(mock_client, "test:layer", out)
            assert os.path.exists(out)
            assert result["file_size"] > 0
            with open(out) as f:
                data = json.load(f)
            assert data["type"] == "FeatureCollection"

    @patch("cli_anything.geoserver.core.export.GeoServerClient")
    def test_export_coverage(self, MockClient):
        from cli_anything.geoserver.core.export import export_coverage
        mock_client = MagicMock()
        # Fake TIFF data (TIFF magic bytes)
        mock_client.wcs_getcoverage.return_value = b"II\x2a\x00" + b"\x00" * 100
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "test.tif")
            result = export_coverage(mock_client, "test:coverage", out)
            assert os.path.exists(out)
            assert result["file_size"] > 0
            with open(out, "rb") as f:
                assert f.read(2) in (b"II", b"MM")  # TIFF byte order


# ── CLI (geoserver_cli.py) ──────────────────────────────────────────────

class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "GeoServer" in result.output or "geoserver" in result.output
        assert "workspace" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_server_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["server", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output
        assert "reload" in result.output


# ── CLI Subprocess ───────────────────────────────────────────────────────

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-geoserver")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "workspace" in result.stdout

    def test_version(self):
        result = self._run(["--version"])
        assert result.returncode == 0
        assert "1.0.0" in result.stdout

    def test_json_workspace_list_no_server(self):
        """Without a running server, workspace list should fail with connection error."""
        result = self._run(
            ["--url", "http://localhost:19999/nonexistent", "--json", "workspace", "list"],
            check=False,
        )
        # Should fail because no server is running at that port
        assert result.returncode != 0 or "error" in result.stderr.lower() or "Cannot connect" in result.stderr
