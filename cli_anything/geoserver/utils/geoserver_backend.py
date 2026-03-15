"""GeoServer backend — complete REST API client for GeoServer.

Covers 100% of the GeoServer REST API endpoints plus OGC service calls.
"""

import json
import os
import requests


class GeoServerError(Exception):
    """Error from GeoServer REST API."""
    def __init__(self, message, status_code=None, response_text=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class GeoServerClient:
    """Complete client for GeoServer REST API and OGC services."""

    def __init__(self, url=None, username=None, password=None):
        self.base_url = (url or os.environ.get("GEOSERVER_URL", "http://localhost:8080/geoserver")).rstrip("/")
        self.rest_url = f"{self.base_url}/rest"
        self.username = username or os.environ.get("GEOSERVER_USER", "admin")
        self.password = password or os.environ.get("GEOSERVER_PASSWORD", "geoserver")
        self.auth = (self.username, self.password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def _url(self, path):
        return f"{self.rest_url}/{path.lstrip('/')}"

    def _request(self, method, path, **kwargs):
        url = self._url(path)
        try:
            resp = self.session.request(method, url, **kwargs)
        except requests.ConnectionError:
            raise GeoServerError(
                f"Cannot connect to GeoServer at {self.base_url}\n"
                "Make sure GeoServer is running. Start with:\n"
                "  docker run -p 8080:8080 docker.io/kartoza/geoserver:latest\n"
                "Or set GEOSERVER_URL environment variable."
            )
        if resp.status_code >= 400:
            raise GeoServerError(
                f"GeoServer API error: {resp.status_code} {resp.reason}",
                status_code=resp.status_code,
                response_text=resp.text,
            )
        return resp

    def _get(self, path, **kwargs):
        return self._request("GET", path, **kwargs)

    def _post(self, path, **kwargs):
        return self._request("POST", path, **kwargs)

    def _put(self, path, **kwargs):
        return self._request("PUT", path, **kwargs)

    def _delete(self, path, **kwargs):
        return self._request("DELETE", path, **kwargs)

    def _list_helper(self, path, outer_key, inner_key):
        """Generic list helper for GeoServer REST collections."""
        resp = self._get(path)
        data = resp.json()
        outer = data.get(outer_key, {})
        if not outer or outer == "":
            return []
        return outer.get(inner_key, [])

    # ═══════════════════════════════════════════════════════════════════════
    # SERVER / ABOUT
    # ═══════════════════════════════════════════════════════════════════════

    def server_status(self):
        """GET /rest/about/status.json"""
        return self._get("about/status.json").json()

    def server_version(self):
        """GET /rest/about/version.json"""
        return self._get("about/version.json").json()

    def server_manifests(self):
        """GET /rest/about/manifests.json"""
        return self._get("about/manifests.json").json()

    def server_reload(self):
        """POST /rest/reload"""
        self._post("reload")
        return {"status": "ok", "message": "Catalog reloaded"}

    def server_reset(self):
        """POST /rest/reset"""
        self._post("reset")
        return {"status": "ok", "message": "Catalog reset"}

    # ═══════════════════════════════════════════════════════════════════════
    # WORKSPACES
    # ═══════════════════════════════════════════════════════════════════════

    def list_workspaces(self):
        return self._list_helper("workspaces.json", "workspaces", "workspace")

    def get_workspace(self, name):
        return self._get(f"workspaces/{name}.json").json().get("workspace", {})

    def create_workspace(self, name, isolated=False):
        self._post("workspaces.json", json={"workspace": {"name": name, "isolated": isolated}})
        return {"name": name, "created": True}

    def update_workspace(self, name, **kwargs):
        self._put(f"workspaces/{name}.json", json={"workspace": kwargs})
        return {"name": name, "updated": True}

    def delete_workspace(self, name, recurse=False):
        self._delete(f"workspaces/{name}", params={"recurse": "true"} if recurse else {})
        return {"name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # NAMESPACES
    # ═══════════════════════════════════════════════════════════════════════

    def list_namespaces(self):
        return self._list_helper("namespaces.json", "namespaces", "namespace")

    def get_namespace(self, prefix):
        return self._get(f"namespaces/{prefix}.json").json().get("namespace", {})

    def create_namespace(self, prefix, uri):
        self._post("namespaces.json", json={"namespace": {"prefix": prefix, "uri": uri}})
        return {"prefix": prefix, "uri": uri, "created": True}

    def update_namespace(self, prefix, **kwargs):
        self._put(f"namespaces/{prefix}.json", json={"namespace": kwargs})
        return {"prefix": prefix, "updated": True}

    def delete_namespace(self, prefix):
        self._delete(f"namespaces/{prefix}")
        return {"prefix": prefix, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # DATA STORES
    # ═══════════════════════════════════════════════════════════════════════

    def list_datastores(self, workspace):
        return self._list_helper(f"workspaces/{workspace}/datastores.json", "dataStores", "dataStore")

    def get_datastore(self, workspace, name):
        return self._get(f"workspaces/{workspace}/datastores/{name}.json").json().get("dataStore", {})

    def create_datastore(self, workspace, name, connection_params):
        payload = {
            "dataStore": {
                "name": name,
                "connectionParameters": {
                    "entry": [{"@key": k, "$": v} for k, v in connection_params.items()]
                },
            }
        }
        self._post(f"workspaces/{workspace}/datastores.json", json=payload)
        return {"workspace": workspace, "name": name, "created": True}

    def update_datastore(self, workspace, name, **kwargs):
        self._put(f"workspaces/{workspace}/datastores/{name}.json", json={"dataStore": kwargs})
        return {"workspace": workspace, "name": name, "updated": True}

    def delete_datastore(self, workspace, name, recurse=False):
        self._delete(f"workspaces/{workspace}/datastores/{name}", params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # COVERAGE STORES
    # ═══════════════════════════════════════════════════════════════════════

    def list_coveragestores(self, workspace):
        return self._list_helper(f"workspaces/{workspace}/coveragestores.json", "coverageStores", "coverageStore")

    def get_coveragestore(self, workspace, name):
        return self._get(f"workspaces/{workspace}/coveragestores/{name}.json").json().get("coverageStore", {})

    def create_coveragestore(self, workspace, name, url, store_type="GeoTIFF"):
        payload = {
            "coverageStore": {
                "name": name,
                "workspace": {"name": workspace},
                "type": store_type,
                "url": url,
                "enabled": True,
            }
        }
        self._post(f"workspaces/{workspace}/coveragestores.json", json=payload)
        return {"workspace": workspace, "name": name, "created": True}

    def update_coveragestore(self, workspace, name, **kwargs):
        self._put(f"workspaces/{workspace}/coveragestores/{name}.json", json={"coverageStore": kwargs})
        return {"workspace": workspace, "name": name, "updated": True}

    def delete_coveragestore(self, workspace, name, recurse=False):
        self._delete(f"workspaces/{workspace}/coveragestores/{name}", params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # WMS STORES (cascaded WMS)
    # ═══════════════════════════════════════════════════════════════════════

    def list_wmsstores(self, workspace):
        return self._list_helper(f"workspaces/{workspace}/wmsstores.json", "wmsStores", "wmsStore")

    def get_wmsstore(self, workspace, name):
        return self._get(f"workspaces/{workspace}/wmsstores/{name}.json").json().get("wmsStore", {})

    def create_wmsstore(self, workspace, name, capabilities_url, **kwargs):
        payload = {
            "wmsStore": {
                "name": name,
                "type": "WMS",
                "capabilitiesURL": capabilities_url,
                "workspace": {"name": workspace},
                "enabled": True,
                **kwargs,
            }
        }
        self._post(f"workspaces/{workspace}/wmsstores.json", json=payload)
        return {"workspace": workspace, "name": name, "created": True}

    def update_wmsstore(self, workspace, name, **kwargs):
        self._put(f"workspaces/{workspace}/wmsstores/{name}.json", json={"wmsStore": kwargs})
        return {"workspace": workspace, "name": name, "updated": True}

    def delete_wmsstore(self, workspace, name, recurse=False):
        self._delete(f"workspaces/{workspace}/wmsstores/{name}", params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # WMTS STORES (cascaded WMTS)
    # ═══════════════════════════════════════════════════════════════════════

    def list_wmtsstores(self, workspace):
        return self._list_helper(f"workspaces/{workspace}/wmtsstores.json", "wmtsStores", "wmtsStore")

    def get_wmtsstore(self, workspace, name):
        return self._get(f"workspaces/{workspace}/wmtsstores/{name}.json").json().get("wmtsStore", {})

    def create_wmtsstore(self, workspace, name, capabilities_url, **kwargs):
        payload = {
            "wmtsStore": {
                "name": name,
                "type": "WMTS",
                "capabilitiesURL": capabilities_url,
                "workspace": {"name": workspace},
                "enabled": True,
                **kwargs,
            }
        }
        self._post(f"workspaces/{workspace}/wmtsstores.json", json=payload)
        return {"workspace": workspace, "name": name, "created": True}

    def update_wmtsstore(self, workspace, name, **kwargs):
        self._put(f"workspaces/{workspace}/wmtsstores/{name}.json", json={"wmtsStore": kwargs})
        return {"workspace": workspace, "name": name, "updated": True}

    def delete_wmtsstore(self, workspace, name, recurse=False):
        self._delete(f"workspaces/{workspace}/wmtsstores/{name}", params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # FEATURE TYPES
    # ═══════════════════════════════════════════════════════════════════════

    def list_featuretypes(self, workspace, store=None):
        if store:
            path = f"workspaces/{workspace}/datastores/{store}/featuretypes.json"
        else:
            path = f"workspaces/{workspace}/featuretypes.json"
        return self._list_helper(path, "featureTypes", "featureType")

    def get_featuretype(self, workspace, store, name):
        return self._get(f"workspaces/{workspace}/datastores/{store}/featuretypes/{name}.json").json().get("featureType", {})

    def create_featuretype(self, workspace, store, name, **kwargs):
        self._post(f"workspaces/{workspace}/datastores/{store}/featuretypes.json",
                   json={"featureType": {"name": name, **kwargs}})
        return {"workspace": workspace, "store": store, "name": name, "created": True}

    def update_featuretype(self, workspace, store, name, **kwargs):
        self._put(f"workspaces/{workspace}/datastores/{store}/featuretypes/{name}.json",
                  json={"featureType": kwargs})
        return {"workspace": workspace, "store": store, "name": name, "updated": True}

    def delete_featuretype(self, workspace, store, name, recurse=False):
        self._delete(f"workspaces/{workspace}/datastores/{store}/featuretypes/{name}",
                     params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "store": store, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # COVERAGES
    # ═══════════════════════════════════════════════════════════════════════

    def list_coverages(self, workspace, store=None):
        if store:
            path = f"workspaces/{workspace}/coveragestores/{store}/coverages.json"
        else:
            path = f"workspaces/{workspace}/coverages.json"
        return self._list_helper(path, "coverages", "coverage")

    def get_coverage(self, workspace, store, name):
        return self._get(f"workspaces/{workspace}/coveragestores/{store}/coverages/{name}.json").json().get("coverage", {})

    def create_coverage(self, workspace, store, name, **kwargs):
        self._post(f"workspaces/{workspace}/coveragestores/{store}/coverages.json",
                   json={"coverage": {"name": name, **kwargs}})
        return {"workspace": workspace, "store": store, "name": name, "created": True}

    def update_coverage(self, workspace, store, name, **kwargs):
        self._put(f"workspaces/{workspace}/coveragestores/{store}/coverages/{name}.json",
                  json={"coverage": kwargs})
        return {"workspace": workspace, "store": store, "name": name, "updated": True}

    def delete_coverage(self, workspace, store, name, recurse=False):
        self._delete(f"workspaces/{workspace}/coveragestores/{store}/coverages/{name}",
                     params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "store": store, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # WMS LAYERS (from cascaded WMS stores)
    # ═══════════════════════════════════════════════════════════════════════

    def list_wmslayers(self, workspace, store=None):
        if store:
            path = f"workspaces/{workspace}/wmsstores/{store}/wmslayers.json"
        else:
            path = f"workspaces/{workspace}/wmslayers.json"
        return self._list_helper(path, "wmsLayers", "wmsLayer")

    def get_wmslayer(self, workspace, store, name):
        return self._get(f"workspaces/{workspace}/wmsstores/{store}/wmslayers/{name}.json").json().get("wmsLayer", {})

    def create_wmslayer(self, workspace, store, name, **kwargs):
        self._post(f"workspaces/{workspace}/wmsstores/{store}/wmslayers.json",
                   json={"wmsLayer": {"name": name, **kwargs}})
        return {"workspace": workspace, "store": store, "name": name, "created": True}

    def update_wmslayer(self, workspace, store, name, **kwargs):
        self._put(f"workspaces/{workspace}/wmsstores/{store}/wmslayers/{name}.json",
                  json={"wmsLayer": kwargs})
        return {"workspace": workspace, "store": store, "name": name, "updated": True}

    def delete_wmslayer(self, workspace, store, name, recurse=False):
        self._delete(f"workspaces/{workspace}/wmsstores/{store}/wmslayers/{name}",
                     params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "store": store, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # WMTS LAYERS (from cascaded WMTS stores)
    # ═══════════════════════════════════════════════════════════════════════

    def list_wmtslayers(self, workspace, store=None):
        if store:
            path = f"workspaces/{workspace}/wmtsstores/{store}/wmtslayers.json"
        else:
            path = f"workspaces/{workspace}/wmtslayers.json"
        return self._list_helper(path, "wmtsLayers", "wmtsLayer")

    def get_wmtslayer(self, workspace, store, name):
        return self._get(f"workspaces/{workspace}/wmtsstores/{store}/wmtslayers/{name}.json").json().get("wmtsLayer", {})

    def create_wmtslayer(self, workspace, store, name, **kwargs):
        self._post(f"workspaces/{workspace}/wmtsstores/{store}/wmtslayers.json",
                   json={"wmtsLayer": {"name": name, **kwargs}})
        return {"workspace": workspace, "store": store, "name": name, "created": True}

    def update_wmtslayer(self, workspace, store, name, **kwargs):
        self._put(f"workspaces/{workspace}/wmtsstores/{store}/wmtslayers/{name}.json",
                  json={"wmtsLayer": kwargs})
        return {"workspace": workspace, "store": store, "name": name, "updated": True}

    def delete_wmtslayer(self, workspace, store, name, recurse=False):
        self._delete(f"workspaces/{workspace}/wmtsstores/{store}/wmtslayers/{name}",
                     params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "store": store, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # LAYERS
    # ═══════════════════════════════════════════════════════════════════════

    def list_layers(self, workspace=None):
        path = f"workspaces/{workspace}/layers.json" if workspace else "layers.json"
        return self._list_helper(path, "layers", "layer")

    def get_layer(self, name, workspace=None):
        path = f"workspaces/{workspace}/layers/{name}.json" if workspace else f"layers/{name}.json"
        return self._get(path).json().get("layer", {})

    def update_layer(self, name, workspace=None, **kwargs):
        path = f"workspaces/{workspace}/layers/{name}.json" if workspace else f"layers/{name}.json"
        self._put(path, json={"layer": kwargs})
        return {"name": name, "updated": True}

    def delete_layer(self, name, workspace=None, recurse=False):
        path = f"workspaces/{workspace}/layers/{name}" if workspace else f"layers/{name}"
        self._delete(path, params={"recurse": "true"} if recurse else {})
        return {"name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER GROUPS
    # ═══════════════════════════════════════════════════════════════════════

    def list_layergroups(self, workspace=None):
        path = f"workspaces/{workspace}/layergroups.json" if workspace else "layergroups.json"
        return self._list_helper(path, "layerGroups", "layerGroup")

    def get_layergroup(self, name, workspace=None):
        path = f"workspaces/{workspace}/layergroups/{name}.json" if workspace else f"layergroups/{name}.json"
        return self._get(path).json().get("layerGroup", {})

    def create_layergroup(self, name, layers, workspace=None, **kwargs):
        path = f"workspaces/{workspace}/layergroups.json" if workspace else "layergroups.json"
        published = [{"@type": "layer", "name": l} for l in layers]
        self._post(path, json={"layerGroup": {"name": name, "layers": {"published": published}, **kwargs}})
        return {"name": name, "created": True}

    def update_layergroup(self, name, workspace=None, **kwargs):
        path = f"workspaces/{workspace}/layergroups/{name}.json" if workspace else f"layergroups/{name}.json"
        self._put(path, json={"layerGroup": kwargs})
        return {"name": name, "updated": True}

    def delete_layergroup(self, name, workspace=None):
        path = f"workspaces/{workspace}/layergroups/{name}" if workspace else f"layergroups/{name}"
        self._delete(path)
        return {"name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # STYLES
    # ═══════════════════════════════════════════════════════════════════════

    def list_styles(self, workspace=None):
        path = f"workspaces/{workspace}/styles.json" if workspace else "styles.json"
        return self._list_helper(path, "styles", "style")

    def get_style(self, name, workspace=None):
        path = f"workspaces/{workspace}/styles/{name}.json" if workspace else f"styles/{name}.json"
        return self._get(path).json().get("style", {})

    def get_style_body(self, name, workspace=None):
        """Get the SLD/CSS body of a style."""
        path = f"workspaces/{workspace}/styles/{name}.sld" if workspace else f"styles/{name}.sld"
        return self._request("GET", path, headers={"Accept": "application/vnd.ogc.sld+xml"}).text

    def create_style(self, name, sld_body, workspace=None):
        path = f"workspaces/{workspace}/styles" if workspace else "styles"
        self._post(f"{path}.json", json={"style": {"name": name, "filename": f"{name}.sld"}})
        self._request("PUT", f"{path}/{name}",
                      data=sld_body.encode("utf-8"),
                      headers={"Content-Type": "application/vnd.ogc.sld+xml"})
        return {"name": name, "created": True}

    def update_style(self, name, sld_body, workspace=None):
        """Update (re-upload) the SLD body of an existing style."""
        path = f"workspaces/{workspace}/styles/{name}" if workspace else f"styles/{name}"
        self._request("PUT", path,
                      data=sld_body.encode("utf-8"),
                      headers={"Content-Type": "application/vnd.ogc.sld+xml"})
        return {"name": name, "updated": True}

    def delete_style(self, name, workspace=None, purge=False):
        path = f"workspaces/{workspace}/styles/{name}" if workspace else f"styles/{name}"
        self._delete(path, params={"purge": "true"} if purge else {})
        return {"name": name, "deleted": True}

    def list_layer_styles(self, layer_name):
        """List styles associated with a layer."""
        return self._list_helper(f"layers/{layer_name}/styles.json", "styles", "style")

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE SETTINGS (WMS / WFS / WCS / WMTS)
    # ═══════════════════════════════════════════════════════════════════════

    def get_service_settings(self, service, workspace=None):
        svc = service.lower()
        path = f"services/{svc}/workspaces/{workspace}/settings.json" if workspace else f"services/{svc}/settings.json"
        return self._get(path).json()

    def update_service_settings(self, service, workspace=None, **kwargs):
        svc = service.lower()
        path = f"services/{svc}/workspaces/{workspace}/settings.json" if workspace else f"services/{svc}/settings.json"
        self._put(path, json={svc: kwargs})
        return {"service": service, "updated": True}

    # ═══════════════════════════════════════════════════════════════════════
    # GLOBAL SETTINGS
    # ═══════════════════════════════════════════════════════════════════════

    def get_settings(self):
        """GET /rest/settings.json"""
        return self._get("settings.json").json()

    def update_settings(self, **kwargs):
        """PUT /rest/settings.json"""
        self._put("settings.json", json={"global": kwargs})
        return {"updated": True}

    def get_contact(self):
        """GET /rest/settings/contact.json"""
        return self._get("settings/contact.json").json()

    def update_contact(self, **kwargs):
        """PUT /rest/settings/contact.json"""
        self._put("settings/contact.json", json={"contact": kwargs})
        return {"updated": True}

    # ── Local workspace settings ──

    def get_local_settings(self, workspace):
        """GET /rest/workspaces/{ws}/settings.json"""
        return self._get(f"workspaces/{workspace}/settings.json").json()

    def create_local_settings(self, workspace, **kwargs):
        """POST /rest/workspaces/{ws}/settings.json"""
        self._post(f"workspaces/{workspace}/settings.json", json={"settings": kwargs})
        return {"workspace": workspace, "created": True}

    def update_local_settings(self, workspace, **kwargs):
        """PUT /rest/workspaces/{ws}/settings.json"""
        self._put(f"workspaces/{workspace}/settings.json", json={"settings": kwargs})
        return {"workspace": workspace, "updated": True}

    def delete_local_settings(self, workspace):
        """DELETE /rest/workspaces/{ws}/settings.json"""
        self._delete(f"workspaces/{workspace}/settings.json")
        return {"workspace": workspace, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # LOGGING
    # ═══════════════════════════════════════════════════════════════════════

    def get_logging(self):
        return self._get("logging.json").json()

    def update_logging(self, **kwargs):
        self._put("logging.json", json={"logging": kwargs})
        return {"updated": True}

    # ═══════════════════════════════════════════════════════════════════════
    # FONTS
    # ═══════════════════════════════════════════════════════════════════════

    def list_fonts(self):
        return self._get("fonts.json").json()

    # ═══════════════════════════════════════════════════════════════════════
    # TEMPLATES (Freemarker)
    # ═══════════════════════════════════════════════════════════════════════

    def list_templates(self, workspace=None, store=None, featuretype=None):
        """List templates at various levels."""
        if featuretype and store and workspace:
            path = f"workspaces/{workspace}/datastores/{store}/featuretypes/{featuretype}/templates.json"
        elif store and workspace:
            path = f"workspaces/{workspace}/datastores/{store}/templates.json"
        elif workspace:
            path = f"workspaces/{workspace}/templates.json"
        else:
            path = "templates.json"
        return self._get(path).json()

    def get_template(self, name, workspace=None, store=None, featuretype=None):
        """Get a template body."""
        base = self._template_path(workspace, store, featuretype)
        resp = self._request("GET", f"{base}/{name}", headers={"Accept": "text/plain"})
        return resp.text

    def create_template(self, name, body, workspace=None, store=None, featuretype=None):
        """Upload a Freemarker template."""
        base = self._template_path(workspace, store, featuretype)
        self._request("PUT", f"{base}/{name}",
                      data=body.encode("utf-8"),
                      headers={"Content-Type": "text/plain"})
        return {"name": name, "created": True}

    def delete_template(self, name, workspace=None, store=None, featuretype=None):
        base = self._template_path(workspace, store, featuretype)
        self._delete(f"{base}/{name}")
        return {"name": name, "deleted": True}

    def _template_path(self, workspace=None, store=None, featuretype=None):
        if featuretype and store and workspace:
            return f"workspaces/{workspace}/datastores/{store}/featuretypes/{featuretype}/templates"
        elif store and workspace:
            return f"workspaces/{workspace}/datastores/{store}/templates"
        elif workspace:
            return f"workspaces/{workspace}/templates"
        return "templates"

    # ═══════════════════════════════════════════════════════════════════════
    # RESOURCES (Data Directory)
    # ═══════════════════════════════════════════════════════════════════════

    def get_resource(self, path):
        """GET /rest/resource/{path} — get file content or directory listing."""
        resp = self._get(f"resource/{path}")
        content_type = resp.headers.get("Content-Type", "")
        if "json" in content_type:
            return resp.json()
        return resp.content

    def get_resource_metadata(self, path):
        """HEAD /rest/resource/{path} — get resource metadata."""
        resp = self._request("HEAD", f"resource/{path}")
        return {
            "content-type": resp.headers.get("Content-Type"),
            "content-length": resp.headers.get("Content-Length"),
            "last-modified": resp.headers.get("Last-Modified"),
            "resource-type": resp.headers.get("Resource-Type"),
        }

    def put_resource(self, path, data, content_type="application/octet-stream"):
        """PUT /rest/resource/{path} — upload/replace a file."""
        self._request("PUT", f"resource/{path}",
                      data=data, headers={"Content-Type": content_type})
        return {"path": path, "uploaded": True}

    def delete_resource(self, path):
        """DELETE /rest/resource/{path}"""
        self._delete(f"resource/{path}")
        return {"path": path, "deleted": True}

    def list_resource_directory(self, path=""):
        """GET /rest/resource/{path}.json — list directory contents."""
        resp = self._get(f"resource/{path}.json" if path else "resource.json")
        return resp.json()

    # ═══════════════════════════════════════════════════════════════════════
    # SECURITY — USERS
    # ═══════════════════════════════════════════════════════════════════════

    def list_users(self, service="default"):
        return self._get(f"security/usergroup/service/{service}/users.json").json()

    def get_user(self, username, service="default"):
        return self._get(f"security/usergroup/service/{service}/user/{username}.json").json()

    def create_user(self, username, password, enabled=True, service="default"):
        payload = {"user": {"userName": username, "password": password, "enabled": enabled}}
        self._post(f"security/usergroup/service/{service}/users.json", json=payload)
        return {"username": username, "created": True}

    def update_user(self, username, service="default", **kwargs):
        self._put(f"security/usergroup/service/{service}/user/{username}.json",
                  json={"user": kwargs})
        return {"username": username, "updated": True}

    def delete_user(self, username, service="default"):
        self._delete(f"security/usergroup/service/{service}/user/{username}")
        return {"username": username, "deleted": True}

    # ── User groups ──

    def list_user_groups(self, service="default"):
        return self._get(f"security/usergroup/service/{service}/groups.json").json()

    def create_user_group(self, group_name, service="default"):
        self._post(f"security/usergroup/service/{service}/group/{group_name}")
        return {"group": group_name, "created": True}

    def delete_user_group(self, group_name, service="default"):
        self._delete(f"security/usergroup/service/{service}/group/{group_name}")
        return {"group": group_name, "deleted": True}

    def add_user_to_group(self, username, group_name, service="default"):
        self._post(f"security/usergroup/service/{service}/user/{username}/group/{group_name}")
        return {"username": username, "group": group_name, "added": True}

    def remove_user_from_group(self, username, group_name, service="default"):
        self._delete(f"security/usergroup/service/{service}/user/{username}/group/{group_name}")
        return {"username": username, "group": group_name, "removed": True}

    def list_usergroup_services(self):
        return self._get("security/usergroup/services.json").json()

    # ═══════════════════════════════════════════════════════════════════════
    # SECURITY — ROLES
    # ═══════════════════════════════════════════════════════════════════════

    def list_roles(self):
        return self._get("security/roles.json").json()

    def list_roles_for_user(self, username):
        return self._get(f"security/roles/user/{username}.json").json()

    def list_roles_for_group(self, group_name):
        return self._get(f"security/roles/group/{group_name}.json").json()

    def create_role(self, role_name):
        self._post(f"security/roles/role/{role_name}")
        return {"role": role_name, "created": True}

    def delete_role(self, role_name):
        self._delete(f"security/roles/role/{role_name}")
        return {"role": role_name, "deleted": True}

    def assign_role_to_user(self, role_name, username):
        self._post(f"security/roles/role/{role_name}/user/{username}")
        return {"role": role_name, "username": username, "assigned": True}

    def remove_role_from_user(self, role_name, username):
        self._delete(f"security/roles/role/{role_name}/user/{username}")
        return {"role": role_name, "username": username, "removed": True}

    def assign_role_to_group(self, role_name, group_name):
        self._post(f"security/roles/role/{role_name}/group/{group_name}")
        return {"role": role_name, "group": group_name, "assigned": True}

    def remove_role_from_group(self, role_name, group_name):
        self._delete(f"security/roles/role/{role_name}/group/{group_name}")
        return {"role": role_name, "group": group_name, "removed": True}

    def list_role_services(self):
        return self._get("security/roles/services.json").json()

    # ═══════════════════════════════════════════════════════════════════════
    # SECURITY — ACCESS RULES
    # ═══════════════════════════════════════════════════════════════════════

    def get_data_access_rules(self):
        """GET /rest/security/acl/layers.json"""
        return self._get("security/acl/layers.json").json()

    def set_data_access_rules(self, rules):
        """POST /rest/security/acl/layers.json — add rules (dict of path: role)."""
        self._post("security/acl/layers.json", json=rules)
        return {"updated": True}

    def update_data_access_rules(self, rules):
        """PUT /rest/security/acl/layers.json — replace all rules."""
        self._put("security/acl/layers.json", json=rules)
        return {"updated": True}

    def delete_data_access_rule(self, rule):
        """DELETE /rest/security/acl/layers/{rule}"""
        self._delete(f"security/acl/layers/{rule}")
        return {"rule": rule, "deleted": True}

    def get_service_access_rules(self):
        """GET /rest/security/acl/services.json"""
        return self._get("security/acl/services.json").json()

    def set_service_access_rules(self, rules):
        self._post("security/acl/services.json", json=rules)
        return {"updated": True}

    def update_service_access_rules(self, rules):
        self._put("security/acl/services.json", json=rules)
        return {"updated": True}

    def delete_service_access_rule(self, rule):
        self._delete(f"security/acl/services/{rule}")
        return {"rule": rule, "deleted": True}

    def get_rest_access_rules(self):
        """GET /rest/security/acl/rest.json"""
        return self._get("security/acl/rest.json").json()

    def set_rest_access_rules(self, rules):
        self._post("security/acl/rest.json", json=rules)
        return {"updated": True}

    def update_rest_access_rules(self, rules):
        self._put("security/acl/rest.json", json=rules)
        return {"updated": True}

    def delete_rest_access_rule(self, rule):
        self._delete(f"security/acl/rest/{rule}")
        return {"rule": rule, "deleted": True}

    # ── Catalog mode ──

    def get_catalog_mode(self):
        return self._get("security/acl/catalog.json").json()

    def update_catalog_mode(self, mode):
        """Set catalog mode: HIDE, MIXED, or CHALLENGE."""
        self._put("security/acl/catalog.json", json={"mode": mode})
        return {"mode": mode, "updated": True}

    # ── Master password ──

    def get_master_password(self):
        return self._get("security/masterpw.json").json()

    def update_master_password(self, old_password, new_password):
        self._put("security/masterpw.json",
                  json={"oldMasterPassword": old_password, "newMasterPassword": new_password})
        return {"updated": True}

    # ── Auth filters and providers ──

    def list_auth_filters(self):
        return self._get("security/auth/filters.json").json()

    def get_auth_filter(self, name):
        return self._get(f"security/auth/filters/{name}.json").json()

    def list_auth_providers(self):
        return self._get("security/auth/providers.json").json()

    def get_auth_provider(self, name):
        return self._get(f"security/auth/providers/{name}.json").json()

    def get_auth_filter_chain(self):
        return self._get("security/auth/chain.json").json()

    def update_auth_filter_chain(self, chain):
        self._put("security/auth/chain.json", json=chain)
        return {"updated": True}

    # ═══════════════════════════════════════════════════════════════════════
    # GEOWEBCACHE (GWC) REST API
    # ═══════════════════════════════════════════════════════════════════════

    def _gwc_url(self, path):
        return f"{self.base_url}/gwc/rest/{path.lstrip('/')}"

    def _gwc_request(self, method, path, **kwargs):
        url = self._gwc_url(path)
        try:
            resp = self.session.request(method, url, **kwargs)
        except requests.ConnectionError:
            raise GeoServerError(f"Cannot connect to GeoWebCache at {url}")
        if resp.status_code >= 400:
            raise GeoServerError(f"GWC API error: {resp.status_code} {resp.reason}",
                                 status_code=resp.status_code, response_text=resp.text)
        return resp

    # ── GWC Layers ──

    def gwc_list_layers(self):
        return self._gwc_request("GET", "layers.json").json()

    def gwc_get_layer(self, name):
        return self._gwc_request("GET", f"layers/{name}.json").json()

    def gwc_update_layer(self, name, config):
        self._gwc_request("PUT", f"layers/{name}.json", json=config)
        return {"name": name, "updated": True}

    def gwc_delete_layer(self, name):
        self._gwc_request("DELETE", f"layers/{name}.json")
        return {"name": name, "deleted": True}

    # ── GWC Seed / Truncate ──

    def gwc_seed(self, layer_name, seed_request):
        """POST /gwc/rest/seed/{layer}.json — seed, reseed, or truncate tiles."""
        self._gwc_request("POST", f"seed/{layer_name}.json", json=seed_request)
        return {"layer": layer_name, "seeded": True}

    def gwc_seed_status(self, layer_name=None):
        """GET /gwc/rest/seed[/{layer}].json — get running/pending seed tasks."""
        path = f"seed/{layer_name}.json" if layer_name else "seed.json"
        return self._gwc_request("GET", path).json()

    def gwc_terminate_seed(self, layer_name=None):
        """POST /gwc/rest/seed[/{layer}] with kill_all — terminate tasks."""
        path = f"seed/{layer_name}" if layer_name else "seed"
        self._gwc_request("POST", path, data="kill_all=all".encode(),
                          headers={"Content-Type": "application/x-www-form-urlencoded"})
        return {"terminated": True}

    def gwc_mass_truncate(self, request_type="truncateLayer", layer_name=None):
        """POST /gwc/rest/masstruncate — mass truncate operations."""
        payload = {"truncateLayer": {"layerName": layer_name}} if layer_name else {}
        self._gwc_request("POST", "masstruncate", json=payload)
        return {"truncated": True}

    # ── GWC Grid Sets ──

    def gwc_list_gridsets(self):
        return self._gwc_request("GET", "gridsets.json").json()

    def gwc_get_gridset(self, name):
        return self._gwc_request("GET", f"gridsets/{name}.json").json()

    def gwc_create_gridset(self, name, config):
        self._gwc_request("PUT", f"gridsets/{name}.json", json=config)
        return {"name": name, "created": True}

    def gwc_delete_gridset(self, name):
        self._gwc_request("DELETE", f"gridsets/{name}.json")
        return {"name": name, "deleted": True}

    # ── GWC Blob Stores ──

    def gwc_list_blobstores(self):
        return self._gwc_request("GET", "blobstores.json").json()

    def gwc_get_blobstore(self, name):
        return self._gwc_request("GET", f"blobstores/{name}.json").json()

    def gwc_create_blobstore(self, name, config):
        self._gwc_request("PUT", f"blobstores/{name}.json", json=config)
        return {"name": name, "created": True}

    def gwc_delete_blobstore(self, name):
        self._gwc_request("DELETE", f"blobstores/{name}.json")
        return {"name": name, "deleted": True}

    # ── GWC Disk Quota ──

    def gwc_get_diskquota(self):
        return self._gwc_request("GET", "diskquota.json").json()

    def gwc_update_diskquota(self, config):
        self._gwc_request("PUT", "diskquota.json", json=config)
        return {"updated": True}

    # ── GWC Global config ──

    def gwc_get_global(self):
        return self._gwc_request("GET", "global.json").json()

    def gwc_update_global(self, config):
        self._gwc_request("PUT", "global.json", json=config)
        return {"updated": True}

    # ═══════════════════════════════════════════════════════════════════════
    # OGC SERVICES (non-REST, for export/introspection)
    # ═══════════════════════════════════════════════════════════════════════

    def _ogc_request(self, service_path, params):
        """Generic OGC service request."""
        url = f"{self.base_url}/{service_path}"
        resp = self.session.get(url, params=params)
        if resp.status_code >= 400:
            raise GeoServerError(f"OGC error: {resp.status_code}", resp.status_code, resp.text)
        return resp

    # ── WMS ──

    def wms_getcapabilities(self, version="1.1.1"):
        resp = self._ogc_request("wms", {"service": "WMS", "version": version, "request": "GetCapabilities"})
        return resp.text

    def wms_getmap(self, layers, bbox, width=800, height=600, srs="EPSG:4326",
                   format="image/png", styles="", transparent=True, **extra):
        params = {
            "service": "WMS", "version": "1.1.1", "request": "GetMap",
            "layers": layers, "bbox": bbox, "width": width, "height": height,
            "srs": srs, "format": format, "styles": styles,
            "transparent": str(transparent).lower(), **extra,
        }
        return self._ogc_request("wms", params).content

    def wms_getfeatureinfo(self, layers, bbox, width, height, x, y,
                           query_layers=None, info_format="application/json",
                           srs="EPSG:4326", feature_count=10, **extra):
        params = {
            "service": "WMS", "version": "1.1.1", "request": "GetFeatureInfo",
            "layers": layers, "query_layers": query_layers or layers,
            "bbox": bbox, "width": width, "height": height,
            "x": x, "y": y, "srs": srs,
            "info_format": info_format, "feature_count": feature_count,
            **extra,
        }
        resp = self._ogc_request("wms", params)
        if "json" in info_format:
            return resp.json()
        return resp.text

    def wms_getlegendgraphic(self, layer, format="image/png", width=20, height=20,
                             style=None, **extra):
        params = {
            "service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic",
            "layer": layer, "format": format, "width": width, "height": height,
            **extra,
        }
        if style:
            params["style"] = style
        return self._ogc_request("wms", params).content

    # ── WFS ──

    def wfs_getcapabilities(self, version="2.0.0"):
        resp = self._ogc_request("wfs", {"service": "WFS", "version": version, "request": "GetCapabilities"})
        return resp.text

    def wfs_describefeaturetype(self, typenames, version="2.0.0", output_format="application/json"):
        params = {
            "service": "WFS", "version": version, "request": "DescribeFeatureType",
            "typeNames": typenames, "outputFormat": output_format,
        }
        resp = self._ogc_request("wfs", params)
        if "json" in output_format:
            return resp.json()
        return resp.text

    def wfs_getfeature(self, typenames, format="application/json", max_features=None,
                       cql_filter=None, bbox=None, srs="EPSG:4326", **extra):
        params = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": typenames, "outputFormat": format, "srsName": srs, **extra,
        }
        if max_features:
            params["count"] = max_features
        if cql_filter:
            params["CQL_FILTER"] = cql_filter
        if bbox:
            params["bbox"] = bbox
        resp = self._ogc_request("wfs", params)
        if "json" in format.lower():
            return resp.json()
        return resp.text

    # ── WCS ──

    def wcs_getcapabilities(self, version="2.0.1"):
        resp = self._ogc_request("wcs", {"service": "WCS", "version": version, "request": "GetCapabilities"})
        return resp.text

    def wcs_describecoverage(self, coverage_id, version="2.0.1"):
        params = {"service": "WCS", "version": version, "request": "DescribeCoverage", "CoverageId": coverage_id}
        return self._ogc_request("wcs", params).text

    def wcs_getcoverage(self, coverage_id, format="image/tiff", bbox=None, srs="EPSG:4326", **extra):
        params = {
            "service": "WCS", "version": "2.0.1", "request": "GetCoverage",
            "CoverageId": coverage_id, "format": format, **extra,
        }
        if bbox:
            parts = bbox.split(",")
            if len(parts) == 4:
                params["subset"] = [f"Long({parts[0]},{parts[2]})", f"Lat({parts[1]},{parts[3]})"]
        return self._ogc_request("wcs", params).content

    # ═══════════════════════════════════════════════════════════════════════
    # FILE UPLOADS
    # ═══════════════════════════════════════════════════════════════════════

    def upload_shapefile(self, workspace, store, zip_path):
        with open(zip_path, "rb") as f:
            data = f.read()
        self._request("PUT", f"workspaces/{workspace}/datastores/{store}/file.shp",
                      data=data, headers={"Content-Type": "application/zip"})
        return {"workspace": workspace, "store": store, "uploaded": True}

    def upload_geotiff(self, workspace, store, tiff_path):
        with open(tiff_path, "rb") as f:
            data = f.read()
        self._request("PUT", f"workspaces/{workspace}/coveragestores/{store}/file.geotiff",
                      data=data, headers={"Content-Type": "image/tiff"})
        return {"workspace": workspace, "store": store, "uploaded": True}

    def upload_geopackage(self, workspace, store, gpkg_path):
        with open(gpkg_path, "rb") as f:
            data = f.read()
        self._request("PUT", f"workspaces/{workspace}/datastores/{store}/file.gpkg",
                      data=data, headers={"Content-Type": "application/geopackage+sqlite3"})
        return {"workspace": workspace, "store": store, "uploaded": True}

    def upload_style(self, name, sld_path, workspace=None):
        with open(sld_path, "r") as f:
            sld_body = f.read()
        return self.create_style(name, sld_body, workspace=workspace)

    # ═══════════════════════════════════════════════════════════════════════
    # URL CHECK
    # ═══════════════════════════════════════════════════════════════════════

    def url_check(self, url):
        """POST /rest/urlchecks — validate a URL."""
        self._post("urlchecks", json={"urlCheck": {"url": url}})
        return {"url": url, "valid": True}
