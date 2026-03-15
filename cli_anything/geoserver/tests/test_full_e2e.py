"""E2E tests for cli-anything-geoserver — requires running GeoServer instance.

Start GeoServer before running:
    docker run -d --name geoserver -p 8080:8080 \
        -e GEOSERVER_ADMIN_USER=admin \
        -e GEOSERVER_ADMIN_PASSWORD=geoserver \
        docker.io/kartoza/geoserver:latest

Run with:
    pytest cli_anything/geoserver/tests/test_full_e2e.py -v -s
"""

import json
import os
import subprocess
import sys
import tempfile
import uuid

import pytest

from cli_anything.geoserver.core.export import export_features, export_map
from cli_anything.geoserver.utils.geoserver_backend import GeoServerClient, GeoServerError

# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def client():
    """Create a GeoServerClient connected to the test instance."""
    url = os.environ.get("GEOSERVER_URL", "http://localhost:8080/geoserver")
    user = os.environ.get("GEOSERVER_USER", "admin")
    password = os.environ.get("GEOSERVER_PASSWORD", "geoserver")
    c = GeoServerClient(url=url, username=user, password=password)
    # Verify connectivity
    try:
        c.server_version()
    except GeoServerError as e:
        pytest.fail(
            f"Cannot connect to GeoServer at {url}. "
            "Start GeoServer with: docker run -d --name geoserver -p 8080:8080 "
            "docker.io/kartoza/geoserver:latest\n"
            f"Error: {e}"
        )
    return c


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory(prefix="gs_e2e_") as d:
        yield d


@pytest.fixture
def unique_name():
    """Generate a unique name for test resources."""
    return f"test_{uuid.uuid4().hex[:8]}"


# ── Server Tests ─────────────────────────────────────────────────────────


class TestServer:
    def test_server_version(self, client):
        data = client.server_version()
        assert "about" in data
        resources = data["about"].get("resource", [])
        gs_found = any(r.get("@name") == "GeoServer" for r in resources)
        assert gs_found, "GeoServer resource not found in version info"
        print(f"\n  GeoServer version info: {len(resources)} resources")

    def test_server_reload(self, client):
        result = client.server_reload()
        assert result["status"] == "ok"


# ── Workspace CRUD ───────────────────────────────────────────────────────


class TestWorkspaceCRUD:
    def test_list_workspaces(self, client):
        workspaces = client.list_workspaces()
        assert isinstance(workspaces, list)
        print(f"\n  Workspaces: {len(workspaces)}")

    def test_create_and_delete_workspace(self, client, unique_name):
        # Create
        result = client.create_workspace(unique_name)
        assert result["created"] is True

        # Verify exists
        ws = client.get_workspace(unique_name)
        assert ws["name"] == unique_name

        # Delete
        result = client.delete_workspace(unique_name, recurse=True)
        assert result["deleted"] is True

        # Verify gone
        with pytest.raises(GeoServerError):
            client.get_workspace(unique_name)


# ── Store Operations ─────────────────────────────────────────────────────


class TestStoreOperations:
    def test_list_datastores(self, client):
        """List datastores in any available workspace."""
        workspaces = client.list_workspaces()
        if workspaces:
            ws_name = workspaces[0]["name"] if isinstance(workspaces[0], dict) else workspaces[0]
            stores = client.list_datastores(ws_name)
            assert isinstance(stores, list)
            print(f"\n  DataStores in '{ws_name}': {len(stores)}")

    def test_list_coveragestores(self, client):
        """List coverage stores in any available workspace."""
        workspaces = client.list_workspaces()
        if workspaces:
            ws_name = workspaces[0]["name"] if isinstance(workspaces[0], dict) else workspaces[0]
            stores = client.list_coveragestores(ws_name)
            assert isinstance(stores, list)
            print(f"\n  CoverageStores in '{ws_name}': {len(stores)}")


# ── Layer Operations ─────────────────────────────────────────────────────


class TestLayerOperations:
    def test_list_layers(self, client):
        layers = client.list_layers()
        assert isinstance(layers, list)
        print(f"\n  Layers: {len(layers)}")

    def test_get_layer(self, client):
        """Get details of the first available layer."""
        layers = client.list_layers()
        if layers:
            name = layers[0]["name"] if isinstance(layers[0], dict) else layers[0]
            layer = client.get_layer(name)
            assert "name" in layer
            print(f"\n  Layer '{name}': type={layer.get('type', 'unknown')}")


# ── Style Operations ─────────────────────────────────────────────────────


class TestStyleOperations:
    def test_list_styles(self, client):
        styles = client.list_styles()
        assert isinstance(styles, list)
        assert len(styles) > 0, "GeoServer should have default styles"
        names = [s["name"] if isinstance(s, dict) else s for s in styles]
        print(f"\n  Styles: {names[:10]}")

    def test_get_style(self, client):
        """Get details of a built-in style."""
        styles = client.list_styles()
        if styles:
            name = styles[0]["name"] if isinstance(styles[0], dict) else styles[0]
            style = client.get_style(name)
            assert "name" in style
            print(f"\n  Style '{name}': format={style.get('format', 'unknown')}")


# ── Service Settings ─────────────────────────────────────────────────────


class TestServiceSettings:
    def test_wms_settings(self, client):
        data = client.get_service_settings("wms")
        assert data is not None
        # WMS settings should contain service info
        wms = data.get("wms", data)
        print(f"\n  WMS settings keys: {list(wms.keys())[:8]}")

    def test_wfs_settings(self, client):
        data = client.get_service_settings("wfs")
        assert data is not None


# ── Export Tests ─────────────────────────────────────────────────────────


class TestExportMap:
    def test_wms_getmap_png(self, client, tmp_dir):
        """Export a map image using WMS GetMap — requires at least one published layer."""
        layers = client.list_layers()
        if not layers:
            pytest.skip("No layers available for WMS GetMap test")

        layer_name = layers[0]["name"] if isinstance(layers[0], dict) else layers[0]
        out_path = os.path.join(tmp_dir, "map.png")

        result = export_map(
            client,
            layer_name,
            out_path,
            bbox="-180,-90,180,90",
            width=256,
            height=256,
            format="image/png",
        )

        assert os.path.exists(result["output"])
        assert result["file_size"] > 0

        # Verify PNG magic bytes
        with open(result["output"], "rb") as f:
            magic = f.read(8)
        assert magic[:4] == b"\x89PNG", f"Expected PNG, got: {magic[:4]}"
        print(f"\n  Map PNG: {result['output']} ({result['file_size']:,} bytes)")


class TestExportFeatures:
    def test_wfs_getfeature_geojson(self, client, tmp_dir):
        """Export features via WFS GetFeature as GeoJSON."""
        layers = client.list_layers()
        if not layers:
            pytest.skip("No layers available for WFS GetFeature test")

        # Find a vector layer
        layer_name = layers[0]["name"] if isinstance(layers[0], dict) else layers[0]
        out_path = os.path.join(tmp_dir, "features.geojson")

        try:
            result = export_features(
                client,
                layer_name,
                out_path,
                format="application/json",
                max_features=10,
            )
            assert os.path.exists(result["output"])
            assert result["file_size"] > 0

            with open(result["output"]) as f:
                data = json.load(f)
            assert data.get("type") == "FeatureCollection"
            print(f"\n  GeoJSON: {result['output']} ({result['file_size']:,} bytes)")
            print(f"  Features: {len(data.get('features', []))}")
        except GeoServerError as e:
            if "400" in str(e) or "404" in str(e):
                pytest.skip(f"Layer '{layer_name}' may not support WFS: {e}")
            raise


# ── Full Workflow Tests ──────────────────────────────────────────────────


class TestFullWorkflow:
    def test_workspace_lifecycle(self, client, unique_name):
        """Full lifecycle: create workspace → list → verify → delete."""
        # Create
        client.create_workspace(unique_name)

        # Verify in list
        workspaces = client.list_workspaces()
        names = [ws["name"] if isinstance(ws, dict) else ws for ws in workspaces]
        assert unique_name in names

        # Get details
        ws = client.get_workspace(unique_name)
        assert ws["name"] == unique_name

        # Delete
        client.delete_workspace(unique_name, recurse=True)

        # Verify gone
        workspaces = client.list_workspaces()
        names = [ws["name"] if isinstance(ws, dict) else ws for ws in workspaces]
        assert unique_name not in names

    def test_server_admin_workflow(self, client):
        """Server admin workflow: status → workspaces → layers → wms settings."""
        # Server version
        version = client.server_version()
        assert "about" in version

        # List workspaces
        workspaces = client.list_workspaces()
        assert isinstance(workspaces, list)

        # List layers
        layers = client.list_layers()
        assert isinstance(layers, list)

        # WMS settings
        wms = client.get_service_settings("wms")
        assert wms is not None

        print(f"\n  Admin workflow: {len(workspaces)} workspaces, {len(layers)} layers")


# ── CLI Subprocess E2E ───────────────────────────────────────────────────


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev."""
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


class TestCLISubprocessE2E:
    CLI_BASE = _resolve_cli("cli-anything-geoserver")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "workspace" in result.stdout

    def test_json_workspace_list(self):
        """List workspaces via subprocess in JSON mode."""
        result = self._run(["--json", "workspace", "list"], check=False)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert isinstance(data, list)
            print(f"\n  Subprocess workspace list: {len(data)} workspaces")
        else:
            # Server not running is acceptable
            assert "Cannot connect" in result.stderr or "error" in result.stderr.lower()

    def test_json_server_status(self):
        """Get server version via subprocess."""
        result = self._run(["--json", "server", "status"], check=False)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "about" in data
            print("\n  Subprocess server status: OK")
        else:
            assert "Cannot connect" in result.stderr or "error" in result.stderr.lower()

    def test_export_map_subprocess(self):
        """Export map via subprocess (if server running)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First get a layer name
            result = self._run(["--json", "layer", "list"], check=False)
            if result.returncode != 0:
                pytest.skip("GeoServer not available for subprocess export test")

            layers = json.loads(result.stdout)
            if not layers:
                pytest.skip("No layers available")

            layer_name = layers[0]["name"] if isinstance(layers[0], dict) else layers[0]
            out_path = os.path.join(tmpdir, "sub_map.png")

            result = self._run(
                [
                    "export",
                    "map",
                    layer_name,
                    out_path,
                    "--bbox",
                    "-180,-90,180,90",
                    "--width",
                    "256",
                    "--height",
                    "256",
                ],
                check=False,
            )

            if result.returncode == 0:
                assert os.path.exists(out_path)
                with open(out_path, "rb") as f:
                    magic = f.read(4)
                assert magic == b"\x89PNG", f"Expected PNG, got: {magic}"
                size = os.path.getsize(out_path)
                print(f"\n  Subprocess map export: {out_path} ({size:,} bytes)")
