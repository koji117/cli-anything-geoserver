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


# ── GeoServerClient — core methods ───────────────────────────────────────

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


# ── GeoServerClient — list_helper for all resource types ─────────────────

class TestListHelper:
    """Test _list_helper for various collection types."""

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_list_namespaces(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"namespaces": {"namespace": [{"prefix": "topp", "uri": "http://topp"}]}}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.list_namespaces()
        assert len(result) == 1
        assert result[0]["prefix"] == "topp"

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_list_wmsstores(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"wmsStores": {"wmsStore": [{"name": "remote_wms"}]}}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.list_wmsstores("topp")
        assert len(result) == 1

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_list_wmtsstores(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"wmtsStores": {"wmtsStore": [{"name": "remote_wmts"}]}}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.list_wmtsstores("topp")
        assert len(result) == 1

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_list_wmslayers(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"wmsLayers": {"wmsLayer": [{"name": "remote_layer"}]}}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.list_wmslayers("topp", "remote_wms")
        assert len(result) == 1

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_list_wmtslayers(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"wmtsLayers": {"wmtsLayer": [{"name": "tiles"}]}}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.list_wmtslayers("topp", "remote_wmts")
        assert len(result) == 1

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_list_empty_collection(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"coverageStores": ""}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.list_coveragestores("ws")
        assert result == []

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_list_featuretypes_with_store(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"featureTypes": {"featureType": [{"name": "roads"}]}}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.list_featuretypes("topp", store="pg_store")
        assert len(result) == 1
        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert "datastores/pg_store" in call_args[0][1]


# ── GeoServerClient — CRUD operations ────────────────────────────────────

class TestCRUDOperations:
    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_create_namespace(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.create_namespace("sf", "http://sf.example.com")
        assert result["prefix"] == "sf"
        assert result["created"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_update_datastore(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.update_datastore("topp", "pg", enabled=False)
        assert result["updated"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_update_coveragestore(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.update_coveragestore("nurc", "dem", enabled=False)
        assert result["updated"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_update_featuretype(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.update_featuretype("topp", "pg", "roads", enabled=False)
        assert result["updated"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_update_coverage(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.update_coverage("nurc", "dem", "DEM", enabled=False)
        assert result["updated"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_delete_coverage(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.delete_coverage("nurc", "dem", "DEM")
        assert result["deleted"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_create_wmsstore(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.create_wmsstore("topp", "remote", "http://example.com/wms?service=WMS&version=1.1.1&request=GetCapabilities")
        assert result["created"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_update_layergroup(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.update_layergroup("spearfish", title="Updated Group")
        assert result["updated"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_update_style(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.update_style("point", "<sld>new body</sld>")
        assert result["updated"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_update_layer(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.update_layer("roads", enabled=False)
        assert result["updated"] is True


# ── GeoServerClient — Security ───────────────────────────────────────────

class TestSecurityMethods:
    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_create_user(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.create_user("testuser", "password123")
        assert result["created"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_delete_user(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.delete_user("testuser")
        assert result["deleted"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_create_role(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.create_role("ROLE_EDITOR")
        assert result["created"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_assign_role_to_user(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.assign_role_to_user("ROLE_EDITOR", "testuser")
        assert result["assigned"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_get_data_access_rules(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"*.*.r": "*", "*.*.w": "ROLE_ADMIN"}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.get_data_access_rules()
        assert "*.*.r" in result

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_update_catalog_mode(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.update_catalog_mode("HIDE")
        assert result["mode"] == "HIDE"


# ── GeoServerClient — GWC ────────────────────────────────────────────────

class TestGWCMethods:
    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._gwc_request")
    def test_gwc_list_layers(self, mock_req):
        mock_req.return_value = MagicMock(json=MagicMock(return_value=["layer1", "layer2"]))
        client = GeoServerClient()
        result = client.gwc_list_layers()
        assert len(result) == 2

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._gwc_request")
    def test_gwc_seed(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.gwc_seed("topp:roads", {"seedRequest": {"type": "seed"}})
        assert result["seeded"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._gwc_request")
    def test_gwc_list_gridsets(self, mock_req):
        mock_req.return_value = MagicMock(json=MagicMock(return_value=["EPSG:4326", "EPSG:900913"]))
        client = GeoServerClient()
        result = client.gwc_list_gridsets()
        assert len(result) == 2

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._gwc_request")
    def test_gwc_mass_truncate(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.gwc_mass_truncate(layer_name="topp:roads")
        assert result["truncated"] is True


# ── GeoServerClient — OGC extended ───────────────────────────────────────

class TestOGCExtended:
    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._ogc_request")
    def test_wms_getcapabilities(self, mock_req):
        mock_req.return_value = MagicMock(text="<WMS_Capabilities/>")
        client = GeoServerClient()
        result = client.wms_getcapabilities()
        assert "WMS_Capabilities" in result

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._ogc_request")
    def test_wfs_getcapabilities(self, mock_req):
        mock_req.return_value = MagicMock(text="<wfs:WFS_Capabilities/>")
        client = GeoServerClient()
        result = client.wfs_getcapabilities()
        assert "WFS_Capabilities" in result

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._ogc_request")
    def test_wcs_getcapabilities(self, mock_req):
        mock_req.return_value = MagicMock(text="<wcs:Capabilities/>")
        client = GeoServerClient()
        result = client.wcs_getcapabilities()
        assert "Capabilities" in result

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._ogc_request")
    def test_wms_getfeatureinfo(self, mock_req):
        mock_req.return_value = MagicMock(json=MagicMock(return_value={"type": "FeatureCollection", "features": []}))
        client = GeoServerClient()
        result = client.wms_getfeatureinfo("topp:roads", "-180,-90,180,90", 800, 600, 400, 300)
        assert result["type"] == "FeatureCollection"

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._ogc_request")
    def test_wfs_describefeaturetype(self, mock_req):
        mock_req.return_value = MagicMock(json=MagicMock(return_value={"featureTypes": []}))
        client = GeoServerClient()
        result = client.wfs_describefeaturetype("topp:roads")
        assert "featureTypes" in result

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._ogc_request")
    def test_wcs_describecoverage(self, mock_req):
        mock_req.return_value = MagicMock(text="<CoverageDescription/>")
        client = GeoServerClient()
        result = client.wcs_describecoverage("nurc:DEM")
        assert "CoverageDescription" in result

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._ogc_request")
    def test_wms_getlegendgraphic(self, mock_req):
        mock_req.return_value = MagicMock(content=b"\x89PNG\r\n")
        client = GeoServerClient()
        result = client.wms_getlegendgraphic("topp:roads")
        assert result[:4] == b"\x89PNG"


# ── GeoServerClient — Resources & Templates ─────────────────────────────

class TestResourcesTemplates:
    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_list_resource_directory(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ResourceDirectory": {"children": {"child": []}}}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.list_resource_directory("styles")
        assert "ResourceDirectory" in result

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_put_resource(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.put_resource("styles/test.sld", b"<sld/>", "application/xml")
        assert result["uploaded"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_delete_resource(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.delete_resource("styles/old.sld")
        assert result["deleted"] is True

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_create_template(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.create_template("header.ftl", "<html>${name}</html>", workspace="topp")
        assert result["created"] is True


# ── GeoServerClient — Settings ───────────────────────────────────────────

class TestSettingsMethods:
    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_get_settings(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"global": {"settings": {}}}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.get_settings()
        assert "global" in result

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_get_contact(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"contact": {"contactPerson": "Admin"}}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.get_contact()
        assert "contact" in result

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_server_manifests(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"about": {"resource": []}}
        mock_req.return_value = mock_resp
        client = GeoServerClient()
        result = client.server_manifests()
        assert "about" in result

    @patch("cli_anything.geoserver.utils.geoserver_backend.GeoServerClient._request")
    def test_server_reset(self, mock_req):
        mock_req.return_value = MagicMock()
        client = GeoServerClient()
        result = client.server_reset()
        assert result["status"] == "ok"


# ── Export (core/export.py) ──────────────────────────────────────────────

class TestExport:
    @patch("cli_anything.geoserver.core.export.GeoServerClient")
    def test_export_map(self, MockClient):
        from cli_anything.geoserver.core.export import export_map
        mock_client = MagicMock()
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
        mock_client.wcs_getcoverage.return_value = b"II\x2a\x00" + b"\x00" * 100
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "test.tif")
            result = export_coverage(mock_client, "test:coverage", out)
            assert os.path.exists(out)
            assert result["file_size"] > 0
            with open(out, "rb") as f:
                assert f.read(2) in (b"II", b"MM")


# ── CLI — all command groups help ────────────────────────────────────────

class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "workspace" in result.output
        assert "namespace" in result.output
        assert "gwc" in result.output
        assert "security" in result.output
        assert "settings" in result.output

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
        assert "reset" in result.output
        assert "manifests" in result.output

    def test_namespace_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["namespace", "--help"])
        assert result.exit_code == 0
        for cmd in ["list", "get", "create", "update", "delete"]:
            assert cmd in result.output

    def test_wmsstore_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["wmsstore", "--help"])
        assert result.exit_code == 0
        for cmd in ["list", "get", "create", "update", "delete"]:
            assert cmd in result.output

    def test_wmtsstore_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["wmtsstore", "--help"])
        assert result.exit_code == 0

    def test_wmslayer_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["wmslayer", "--help"])
        assert result.exit_code == 0

    def test_wmtslayer_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["wmtslayer", "--help"])
        assert result.exit_code == 0

    def test_resource_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["resource", "--help"])
        assert result.exit_code == 0
        for cmd in ["list", "get", "put", "delete"]:
            assert cmd in result.output

    def test_template_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["template", "--help"])
        assert result.exit_code == 0

    def test_security_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["security", "--help"])
        assert result.exit_code == 0
        for sub in ["user", "group", "role", "rules", "catalog-mode", "master-password"]:
            assert sub in result.output

    def test_gwc_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["gwc", "--help"])
        assert result.exit_code == 0
        for sub in ["layer", "seed", "gridset", "blobstore", "diskquota", "global"]:
            assert sub in result.output

    def test_settings_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["settings", "--help"])
        assert result.exit_code == 0
        for sub in ["get", "update", "logging-get", "fonts", "contact-get"]:
            assert sub in result.output

    def test_export_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0
        for sub in ["map", "features", "coverage", "capabilities", "featureinfo", "legendgraphic"]:
            assert sub in result.output

    def test_store_has_update_commands(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["store", "--help"])
        assert result.exit_code == 0
        assert "update-datastore" in result.output
        assert "update-coveragestore" in result.output

    def test_layer_has_update(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["layer", "--help"])
        assert result.exit_code == 0
        assert "update" in result.output

    def test_style_has_update(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["style", "--help"])
        assert result.exit_code == 0
        assert "update" in result.output

    def test_layergroup_has_update(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["layergroup", "--help"])
        assert result.exit_code == 0
        assert "update" in result.output

    def test_workspace_has_update(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["workspace", "--help"])
        assert result.exit_code == 0
        assert "update" in result.output

    def test_service_has_update(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["service", "--help"])
        assert result.exit_code == 0
        assert "update" in result.output


# ── CLI Subprocess ───────────────────────────────────────────────────────

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
        assert "gwc" in result.stdout
        assert "security" in result.stdout

    def test_version(self):
        result = self._run(["--version"])
        assert result.returncode == 0
        assert "1.0.0" in result.stdout

    def test_json_workspace_list_no_server(self):
        result = self._run(
            ["--url", "http://localhost:19999/nonexistent", "--json", "workspace", "list"],
            check=False,
        )
        assert result.returncode != 0 or "error" in result.stderr.lower() or "Cannot connect" in result.stderr

    def test_all_command_groups_help(self):
        """Verify all 18 command groups respond to --help via subprocess."""
        groups = [
            "server", "workspace", "namespace", "store", "layer", "style",
            "layergroup", "service", "export", "wmsstore", "wmtsstore",
            "wmslayer", "wmtslayer", "resource", "template", "security",
            "gwc", "settings",
        ]
        for group in groups:
            result = self._run([group, "--help"])
            assert result.returncode == 0, f"{group} --help failed"
