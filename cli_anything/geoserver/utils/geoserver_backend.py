"""GeoServer backend — REST API client for GeoServer."""

import json
import os
import requests
from urllib.parse import urljoin


class GeoServerError(Exception):
    """Error from GeoServer REST API."""
    def __init__(self, message, status_code=None, response_text=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class GeoServerClient:
    """Client for GeoServer REST API."""

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
        """Build full REST URL."""
        return f"{self.rest_url}/{path.lstrip('/')}"

    def _request(self, method, path, **kwargs):
        """Make HTTP request to GeoServer REST API."""
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

    # ── Server ──
    def server_status(self):
        """Get server status/about info."""
        resp = self._get("about/status.json")
        return resp.json()

    def server_reload(self):
        """Reload the GeoServer catalog."""
        self._post("reload")
        return {"status": "ok", "message": "Catalog reloaded"}

    def server_version(self):
        """Get GeoServer version info."""
        resp = self._get("about/version.json")
        return resp.json()

    # ── Workspaces ──
    def list_workspaces(self):
        resp = self._get("workspaces.json")
        data = resp.json()
        ws = data.get("workspaces", {})
        if not ws or ws == "":
            return []
        return ws.get("workspace", [])

    def get_workspace(self, name):
        resp = self._get(f"workspaces/{name}.json")
        return resp.json().get("workspace", {})

    def create_workspace(self, name, isolated=False):
        payload = {"workspace": {"name": name, "isolated": isolated}}
        self._post("workspaces.json", json=payload)
        return {"name": name, "created": True}

    def delete_workspace(self, name, recurse=False):
        params = {"recurse": "true"} if recurse else {}
        self._delete(f"workspaces/{name}", params=params)
        return {"name": name, "deleted": True}

    def update_workspace(self, name, **kwargs):
        payload = {"workspace": kwargs}
        self._put(f"workspaces/{name}.json", json=payload)
        return {"name": name, "updated": True}

    # ── Data Stores ──
    def list_datastores(self, workspace):
        resp = self._get(f"workspaces/{workspace}/datastores.json")
        data = resp.json()
        ds = data.get("dataStores", {})
        if not ds or ds == "":
            return []
        return ds.get("dataStore", [])

    def get_datastore(self, workspace, name):
        resp = self._get(f"workspaces/{workspace}/datastores/{name}.json")
        return resp.json().get("dataStore", {})

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

    def delete_datastore(self, workspace, name, recurse=False):
        params = {"recurse": "true"} if recurse else {}
        self._delete(f"workspaces/{workspace}/datastores/{name}", params=params)
        return {"workspace": workspace, "name": name, "deleted": True}

    # ── Coverage Stores ──
    def list_coveragestores(self, workspace):
        resp = self._get(f"workspaces/{workspace}/coveragestores.json")
        data = resp.json()
        cs = data.get("coverageStores", {})
        if not cs or cs == "":
            return []
        return cs.get("coverageStore", [])

    def get_coveragestore(self, workspace, name):
        resp = self._get(f"workspaces/{workspace}/coveragestores/{name}.json")
        return resp.json().get("coverageStore", {})

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

    def delete_coveragestore(self, workspace, name, recurse=False):
        params = {"recurse": "true"} if recurse else {}
        self._delete(f"workspaces/{workspace}/coveragestores/{name}", params=params)
        return {"workspace": workspace, "name": name, "deleted": True}

    # ── Feature Types ──
    def list_featuretypes(self, workspace, store=None):
        if store:
            path = f"workspaces/{workspace}/datastores/{store}/featuretypes.json"
        else:
            path = f"workspaces/{workspace}/featuretypes.json"
        resp = self._get(path)
        data = resp.json()
        ft = data.get("featureTypes", {})
        if not ft or ft == "":
            return []
        return ft.get("featureType", [])

    def get_featuretype(self, workspace, store, name):
        resp = self._get(f"workspaces/{workspace}/datastores/{store}/featuretypes/{name}.json")
        return resp.json().get("featureType", {})

    def create_featuretype(self, workspace, store, name, **kwargs):
        payload = {"featureType": {"name": name, **kwargs}}
        self._post(f"workspaces/{workspace}/datastores/{store}/featuretypes.json", json=payload)
        return {"workspace": workspace, "store": store, "name": name, "created": True}

    def delete_featuretype(self, workspace, store, name, recurse=False):
        params = {"recurse": "true"} if recurse else {}
        self._delete(f"workspaces/{workspace}/datastores/{store}/featuretypes/{name}", params=params)
        return {"workspace": workspace, "store": store, "name": name, "deleted": True}

    # ── Coverages ──
    def list_coverages(self, workspace, store=None):
        if store:
            path = f"workspaces/{workspace}/coveragestores/{store}/coverages.json"
        else:
            path = f"workspaces/{workspace}/coverages.json"
        resp = self._get(path)
        data = resp.json()
        cv = data.get("coverages", {})
        if not cv or cv == "":
            return []
        return cv.get("coverage", [])

    def get_coverage(self, workspace, store, name):
        resp = self._get(f"workspaces/{workspace}/coveragestores/{store}/coverages/{name}.json")
        return resp.json().get("coverage", {})

    def create_coverage(self, workspace, store, name, **kwargs):
        payload = {"coverage": {"name": name, **kwargs}}
        self._post(f"workspaces/{workspace}/coveragestores/{store}/coverages.json", json=payload)
        return {"workspace": workspace, "store": store, "name": name, "created": True}

    # ── Layers ──
    def list_layers(self, workspace=None):
        if workspace:
            path = f"workspaces/{workspace}/layers.json"
        else:
            path = "layers.json"
        resp = self._get(path)
        data = resp.json()
        ly = data.get("layers", {})
        if not ly or ly == "":
            return []
        return ly.get("layer", [])

    def get_layer(self, name, workspace=None):
        if workspace:
            path = f"workspaces/{workspace}/layers/{name}.json"
        else:
            path = f"layers/{name}.json"
        resp = self._get(path)
        return resp.json().get("layer", {})

    def update_layer(self, name, workspace=None, **kwargs):
        if workspace:
            path = f"workspaces/{workspace}/layers/{name}.json"
        else:
            path = f"layers/{name}.json"
        payload = {"layer": kwargs}
        self._put(path, json=payload)
        return {"name": name, "updated": True}

    def delete_layer(self, name, workspace=None, recurse=False):
        if workspace:
            path = f"workspaces/{workspace}/layers/{name}"
        else:
            path = f"layers/{name}"
        params = {"recurse": "true"} if recurse else {}
        self._delete(path, params=params)
        return {"name": name, "deleted": True}

    # ── Layer Groups ──
    def list_layergroups(self, workspace=None):
        if workspace:
            path = f"workspaces/{workspace}/layergroups.json"
        else:
            path = "layergroups.json"
        resp = self._get(path)
        data = resp.json()
        lg = data.get("layerGroups", {})
        if not lg or lg == "":
            return []
        return lg.get("layerGroup", [])

    def get_layergroup(self, name, workspace=None):
        if workspace:
            path = f"workspaces/{workspace}/layergroups/{name}.json"
        else:
            path = f"layergroups/{name}.json"
        resp = self._get(path)
        return resp.json().get("layerGroup", {})

    def create_layergroup(self, name, layers, workspace=None, **kwargs):
        if workspace:
            path = f"workspaces/{workspace}/layergroups.json"
        else:
            path = "layergroups.json"
        published = [{"@type": "layer", "name": l} for l in layers]
        payload = {
            "layerGroup": {
                "name": name,
                "layers": {"published": published},
                **kwargs,
            }
        }
        self._post(path, json=payload)
        return {"name": name, "created": True}

    def delete_layergroup(self, name, workspace=None):
        if workspace:
            path = f"workspaces/{workspace}/layergroups/{name}"
        else:
            path = f"layergroups/{name}"
        self._delete(path)
        return {"name": name, "deleted": True}

    # ── Styles ──
    def list_styles(self, workspace=None):
        if workspace:
            path = f"workspaces/{workspace}/styles.json"
        else:
            path = "styles.json"
        resp = self._get(path)
        data = resp.json()
        st = data.get("styles", {})
        if not st or st == "":
            return []
        return st.get("style", [])

    def get_style(self, name, workspace=None):
        if workspace:
            path = f"workspaces/{workspace}/styles/{name}.json"
        else:
            path = f"styles/{name}.json"
        resp = self._get(path)
        return resp.json().get("style", {})

    def get_style_body(self, name, workspace=None):
        """Get the SLD/CSS body of a style."""
        if workspace:
            path = f"workspaces/{workspace}/styles/{name}.sld"
        else:
            path = f"styles/{name}.sld"
        resp = self._request("GET", path, headers={"Accept": "application/vnd.ogc.sld+xml"})
        return resp.text

    def create_style(self, name, sld_body, workspace=None):
        if workspace:
            path = f"workspaces/{workspace}/styles"
        else:
            path = "styles"
        # First create the style entry
        self._post(f"{path}.json", json={"style": {"name": name, "filename": f"{name}.sld"}})
        # Then upload the SLD body
        self._request("PUT", f"{path}/{name}",
                      data=sld_body.encode("utf-8"),
                      headers={"Content-Type": "application/vnd.ogc.sld+xml"})
        return {"name": name, "created": True}

    def delete_style(self, name, workspace=None, purge=False):
        if workspace:
            path = f"workspaces/{workspace}/styles/{name}"
        else:
            path = f"styles/{name}"
        params = {"purge": "true"} if purge else {}
        self._delete(path, params=params)
        return {"name": name, "deleted": True}

    # ── Service Settings ──
    def get_service_settings(self, service, workspace=None):
        """Get WMS/WFS/WCS/WMTS settings."""
        service = service.lower()
        if workspace:
            path = f"services/{service}/workspaces/{workspace}/settings.json"
        else:
            path = f"services/{service}/settings.json"
        resp = self._get(path)
        return resp.json()

    def update_service_settings(self, service, workspace=None, **kwargs):
        service_lower = service.lower()
        if workspace:
            path = f"services/{service_lower}/workspaces/{workspace}/settings.json"
        else:
            path = f"services/{service_lower}/settings.json"
        key = service_lower
        payload = {key: kwargs}
        self._put(path, json=payload)
        return {"service": service, "updated": True}

    # ── Settings ──
    def get_settings(self):
        resp = self._get("settings.json")
        return resp.json()

    def update_settings(self, **kwargs):
        payload = {"global": kwargs}
        self._put("settings.json", json=payload)
        return {"updated": True}

    def get_logging(self):
        resp = self._get("logging.json")
        return resp.json()

    def update_logging(self, **kwargs):
        payload = {"logging": kwargs}
        self._put("logging.json", json=payload)
        return {"updated": True}

    # ── Fonts ──
    def list_fonts(self):
        resp = self._get("fonts.json")
        return resp.json()

    # ── Security ──
    def list_users(self, service="default"):
        resp = self._get(f"security/usergroup/service/{service}/users.json")
        return resp.json()

    def list_roles(self):
        resp = self._get("security/roles.json")
        return resp.json()

    # ── OGC Services (non-REST, for export) ──
    def wms_getmap(self, layers, bbox, width=800, height=600, srs="EPSG:4326",
                   format="image/png", styles="", transparent=True, **extra):
        """Download a map image via WMS GetMap."""
        params = {
            "service": "WMS",
            "version": "1.1.1",
            "request": "GetMap",
            "layers": layers,
            "bbox": bbox,
            "width": width,
            "height": height,
            "srs": srs,
            "format": format,
            "styles": styles,
            "transparent": str(transparent).lower(),
            **extra,
        }
        url = f"{self.base_url}/wms"
        resp = self.session.get(url, params=params)
        if resp.status_code >= 400:
            raise GeoServerError(f"WMS GetMap error: {resp.status_code}", resp.status_code, resp.text)
        return resp.content

    def wfs_getfeature(self, typenames, format="application/json", max_features=None,
                       cql_filter=None, bbox=None, srs="EPSG:4326", **extra):
        """Download features via WFS GetFeature."""
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": typenames,
            "outputFormat": format,
            "srsName": srs,
            **extra,
        }
        if max_features:
            params["count"] = max_features
        if cql_filter:
            params["CQL_FILTER"] = cql_filter
        if bbox:
            params["bbox"] = bbox
        url = f"{self.base_url}/wfs"
        resp = self.session.get(url, params=params)
        if resp.status_code >= 400:
            raise GeoServerError(f"WFS GetFeature error: {resp.status_code}", resp.status_code, resp.text)
        if "json" in format.lower():
            return resp.json()
        return resp.text

    def wcs_getcoverage(self, coverage_id, format="image/tiff", bbox=None, srs="EPSG:4326", **extra):
        """Download raster data via WCS GetCoverage."""
        params = {
            "service": "WCS",
            "version": "2.0.1",
            "request": "GetCoverage",
            "CoverageId": coverage_id,
            "format": format,
            **extra,
        }
        if bbox:
            # WCS 2.0 uses subsets
            parts = bbox.split(",")
            if len(parts) == 4:
                params["subset"] = [f"Long({parts[0]},{parts[2]})", f"Lat({parts[1]},{parts[3]})"]
        url = f"{self.base_url}/wcs"
        resp = self.session.get(url, params=params)
        if resp.status_code >= 400:
            raise GeoServerError(f"WCS GetCoverage error: {resp.status_code}", resp.status_code, resp.text)
        return resp.content

    # ── Resource Upload ──
    def upload_shapefile(self, workspace, store, zip_path):
        """Upload a zipped shapefile to create a datastore."""
        with open(zip_path, "rb") as f:
            data = f.read()
        path = f"workspaces/{workspace}/datastores/{store}/file.shp"
        self._request("PUT", path, data=data,
                      headers={"Content-Type": "application/zip"})
        return {"workspace": workspace, "store": store, "uploaded": True}

    def upload_geotiff(self, workspace, store, tiff_path):
        """Upload a GeoTIFF to create a coverage store."""
        with open(tiff_path, "rb") as f:
            data = f.read()
        path = f"workspaces/{workspace}/coveragestores/{store}/file.geotiff"
        self._request("PUT", path, data=data,
                      headers={"Content-Type": "image/tiff"})
        return {"workspace": workspace, "store": store, "uploaded": True}

    def upload_style(self, name, sld_path, workspace=None):
        """Upload an SLD file as a style."""
        with open(sld_path, "r") as f:
            sld_body = f.read()
        return self.create_style(name, sld_body, workspace=workspace)
