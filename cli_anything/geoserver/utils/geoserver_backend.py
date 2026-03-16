"""GeoServer backend — complete REST API client for GeoServer.

Covers 100% of the GeoServer REST API endpoints plus OGC service calls.
"""

import os

import requests


class GeoServerError(Exception):
    """Error from GeoServer REST API."""

    def __init__(self, message, status_code=None, response_text=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class GeoServerClient:
    """Complete client for GeoServer REST API and OGC services.

    Covers 100% of the GeoServer REST API, GeoWebCache REST API, and OGC
    service endpoints (WMS, WFS, WCS).

    Example::

        # Using environment variables (GEOSERVER_URL, GEOSERVER_USER, GEOSERVER_PASSWORD)
        client = GeoServerClient()

        # Explicit connection
        client = GeoServerClient(
            url="http://localhost:8080/geoserver",
            username="admin",
            password="geoserver",
        )

        # List workspaces
        client.list_workspaces()

        # Create a PostGIS datastore
        client.create_datastore("my_ws", "pg_db", {
            "host": "localhost", "port": "5432", "database": "geodata",
            "user": "geo", "passwd": "secret", "dbtype": "postgis",
        })
    """

    def __init__(self, url=None, username=None, password=None):
        self.base_url = (url or os.environ.get("GEOSERVER_URL", "http://localhost:8080/geoserver")).rstrip("/")
        self.rest_url = f"{self.base_url}/rest"
        self.username = username or os.environ.get("GEOSERVER_USER", "admin")
        self.password = password or os.environ.get("GEOSERVER_PASSWORD", "geoserver")
        self.auth = (self.username, self.password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def _url(self, path):
        return f"{self.rest_url}/{path.lstrip('/')}"

    def _request(self, method, path, **kwargs):
        url = self._url(path)
        try:
            resp = self.session.request(method, url, **kwargs)
        except requests.ConnectionError as exc:
            raise GeoServerError(
                f"Cannot connect to GeoServer at {self.base_url}\n"
                "Make sure GeoServer is running. Start with:\n"
                "  docker run -p 8080:8080 docker.io/kartoza/geoserver:latest\n"
                "Or set GEOSERVER_URL environment variable."
            ) from exc
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

    @staticmethod
    def _build_payload(explicit, extras):
        """Merge explicit params (dropping None) with extras."""
        payload = {k: v for k, v in explicit.items() if v is not None}
        payload.update(extras)
        return payload

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
        """GET /rest/about/status.json — module status of all GeoServer components.

        Returns a list of module entries with name, enabled status, version,
        and component info.

        Example::

            status = client.server_status()
            for mod in status["about"]["resource"]:
                print(mod["@name"], mod.get("Version", ""))
        """
        return self._get("about/status.json").json()

    def server_version(self):
        """GET /rest/about/version.json — GeoServer and GeoTools version info.

        Example::

            info = client.server_version()
            for r in info["about"]["resource"]:
                print(r["@name"], r.get("Version", ""))
            # GeoServer 2.26.1, GeoTools 32.1, GeoWebCache 1.26.1
        """
        return self._get("about/version.json").json()

    def server_manifests(self):
        """GET /rest/about/manifests.json — JAR manifests for all loaded libraries.

        Example::

            manifests = client.server_manifests()
        """
        return self._get("about/manifests.json").json()

    def server_reload(self):
        """POST /rest/reload — reload the GeoServer catalog from disk.

        Forces GeoServer to re-read all configuration from the data directory.
        Useful after manual XML edits or restoring a backup.

        Example::

            client.server_reload()
        """
        self._post("reload")
        return {"status": "ok", "message": "Catalog reloaded"}

    def server_reset(self):
        """POST /rest/reset — reset all resource and store caches.

        Clears all cached data connections and state. More aggressive than
        reload — use when stores are returning stale data.

        Example::

            client.server_reset()
        """
        self._post("reset")
        return {"status": "ok", "message": "Catalog reset"}

    # ═══════════════════════════════════════════════════════════════════════
    # WORKSPACES
    # ═══════════════════════════════════════════════════════════════════════

    def list_workspaces(self):
        """GET /rest/workspaces.json — list all workspaces.

        Example::

            workspaces = client.list_workspaces()
            for ws in workspaces:
                print(ws["name"])
        """
        return self._list_helper("workspaces.json", "workspaces", "workspace")

    def get_workspace(self, name):
        """GET /rest/workspaces/{name}.json — get workspace details.

        Args:
            name: Workspace name.

        Example::

            ws = client.get_workspace("topp")
            print(ws["name"], ws.get("isolated", False))
        """
        return self._get(f"workspaces/{name}.json").json().get("workspace", {})

    def create_workspace(self, name, isolated=False):
        """POST /rest/workspaces.json — create a new workspace.

        Args:
            name: Workspace name (also creates a matching namespace).
            isolated: If True, the workspace is isolated — its layers are
                only accessible via virtual OGC services scoped to this
                workspace (e.g. ``/geoserver/my_ws/wms``).

        Example::

            client.create_workspace("my_project")
            client.create_workspace("sandbox", isolated=True)
        """
        self._post("workspaces.json", json={"workspace": {"name": name, "isolated": isolated}})
        return {"name": name, "created": True}

    def update_workspace(self, name, *, isolated=None, **kwargs):
        """PUT /rest/workspaces/{name}.json — update workspace properties.

        Args:
            name: Current workspace name.
            isolated: Toggle workspace isolation.
            **kwargs: Additional workspace properties.

        Example::

            client.update_workspace("my_ws", isolated=True)
        """
        payload = self._build_payload({"isolated": isolated}, kwargs)
        self._put(f"workspaces/{name}.json", json={"workspace": payload})
        return {"name": name, "updated": True}

    def delete_workspace(self, name, recurse=False):
        """DELETE /rest/workspaces/{name} — delete a workspace.

        Args:
            name: Workspace name.
            recurse: If True, recursively delete all stores, layers, and
                styles contained in the workspace.

        Example::

            client.delete_workspace("old_project", recurse=True)
        """
        self._delete(f"workspaces/{name}", params={"recurse": "true"} if recurse else {})
        return {"name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # NAMESPACES
    # ═══════════════════════════════════════════════════════════════════════

    def list_namespaces(self):
        """GET /rest/namespaces.json — list all namespaces.

        Each workspace has a 1:1 namespace. The namespace prefix matches the
        workspace name and the URI is used in WFS XML output.

        Example::

            namespaces = client.list_namespaces()
            for ns in namespaces:
                print(ns["prefix"], ns.get("uri", ""))
        """
        return self._list_helper("namespaces.json", "namespaces", "namespace")

    def get_namespace(self, prefix):
        """GET /rest/namespaces/{prefix}.json — get namespace details.

        Args:
            prefix: Namespace prefix (same as workspace name).

        Example::

            ns = client.get_namespace("topp")
            print(ns["uri"])  # e.g. "http://www.openplans.org/topp"
        """
        return self._get(f"namespaces/{prefix}.json").json().get("namespace", {})

    def create_namespace(self, prefix, uri):
        """POST /rest/namespaces.json — create a new namespace.

        Args:
            prefix: Namespace prefix (also creates a matching workspace).
            uri: Namespace URI used in WFS/WCS XML output,
                e.g. ``"http://example.com/my_project"``.

        Example::

            client.create_namespace("my_project", "http://example.com/my_project")
        """
        self._post("namespaces.json", json={"namespace": {"prefix": prefix, "uri": uri}})
        return {"prefix": prefix, "uri": uri, "created": True}

    def update_namespace(self, prefix, *, uri=None, isolated=None, **kwargs):
        """PUT /rest/namespaces/{prefix}.json — update namespace properties.

        Args:
            prefix: Current namespace prefix.
            uri: New namespace URI.
            isolated: Toggle namespace isolation.
            **kwargs: Additional namespace properties.

        Example::

            client.update_namespace("topp", uri="http://new-uri.example.com/topp")
        """
        payload = self._build_payload({"uri": uri, "isolated": isolated}, kwargs)
        self._put(f"namespaces/{prefix}.json", json={"namespace": payload})
        return {"prefix": prefix, "updated": True}

    def delete_namespace(self, prefix):
        """DELETE /rest/namespaces/{prefix} — delete a namespace.

        Args:
            prefix: Namespace prefix to delete.

        Example::

            client.delete_namespace("old_ns")
        """
        self._delete(f"namespaces/{prefix}")
        return {"prefix": prefix, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # DATA STORES
    # ═══════════════════════════════════════════════════════════════════════

    def list_datastores(self, workspace):
        """GET /rest/workspaces/{ws}/datastores.json — list data stores.

        Args:
            workspace: Workspace name.

        Example::

            stores = client.list_datastores("topp")
            for s in stores:
                print(s["name"])
        """
        return self._list_helper(f"workspaces/{workspace}/datastores.json", "dataStores", "dataStore")

    def get_datastore(self, workspace, name):
        """GET /rest/workspaces/{ws}/datastores/{name}.json — get data store details.

        Args:
            workspace: Workspace name.
            name: Data store name.

        Example::

            ds = client.get_datastore("topp", "pg_db")
            print(ds["type"])  # e.g. "PostGIS"
        """
        return self._get(f"workspaces/{workspace}/datastores/{name}.json").json().get("dataStore", {})

    def create_datastore(self, workspace, name, connection_params):
        """POST /rest/workspaces/{ws}/datastores.json — create a new data store.

        Args:
            workspace: Target workspace name.
            name: Data store name.
            connection_params: Dict of connection parameters. Common configurations:

                **PostGIS**::

                    {"host": "localhost", "port": "5432", "database": "geodata",
                     "schema": "public", "user": "geo", "passwd": "secret",
                     "dbtype": "postgis", "Expose primary keys": "true"}

                **Shapefile directory**::

                    {"url": "file:data/shapefiles", "dbtype": "shapefile"}

                **GeoPackage**::

                    {"database": "file:data/my.gpkg", "dbtype": "geopkg"}

        Example::

            client.create_datastore("my_ws", "pg_db", {
                "host": "db.example.com", "port": "5432",
                "database": "geodata", "user": "geo", "passwd": "secret",
                "dbtype": "postgis",
            })
        """
        payload = {
            "dataStore": {
                "name": name,
                "connectionParameters": {"entry": [{"@key": k, "$": v} for k, v in connection_params.items()]},
            }
        }
        self._post(f"workspaces/{workspace}/datastores.json", json=payload)
        return {"workspace": workspace, "name": name, "created": True}

    def update_datastore(self, workspace, name, *, description=None, enabled=None, **kwargs):
        """PUT /rest/workspaces/{ws}/datastores/{name}.json — update a data store.

        Args:
            workspace: Workspace name.
            name: Data store name.
            description: Human-readable description.
            enabled: Enable/disable the store (disabled stores hide all their layers).
            **kwargs: Additional data store properties.

        Example::

            client.update_datastore("topp", "pg_db", enabled=False)
            client.update_datastore("topp", "pg_db", description="Production PostGIS")
        """
        payload = self._build_payload({"description": description, "enabled": enabled}, kwargs)
        self._put(f"workspaces/{workspace}/datastores/{name}.json", json={"dataStore": payload})
        return {"workspace": workspace, "name": name, "updated": True}

    def delete_datastore(self, workspace, name, recurse=False):
        """DELETE /rest/workspaces/{ws}/datastores/{name} — delete a data store.

        Args:
            workspace: Workspace name.
            name: Data store name.
            recurse: If True, also delete all feature types and layers
                published from this store.

        Example::

            client.delete_datastore("topp", "old_db", recurse=True)
        """
        self._delete(f"workspaces/{workspace}/datastores/{name}", params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # COVERAGE STORES
    # ═══════════════════════════════════════════════════════════════════════

    def list_coveragestores(self, workspace):
        """GET /rest/workspaces/{ws}/coveragestores.json — list coverage stores.

        Args:
            workspace: Workspace name.

        Example::

            stores = client.list_coveragestores("nurc")
            for s in stores:
                print(s["name"])
        """
        return self._list_helper(f"workspaces/{workspace}/coveragestores.json", "coverageStores", "coverageStore")

    def get_coveragestore(self, workspace, name):
        """GET /rest/workspaces/{ws}/coveragestores/{name}.json — get coverage store details.

        Args:
            workspace: Workspace name.
            name: Coverage store name.

        Example::

            cs = client.get_coveragestore("nurc", "dem")
            print(cs["type"], cs.get("url", ""))
        """
        return self._get(f"workspaces/{workspace}/coveragestores/{name}.json").json().get("coverageStore", {})

    def create_coveragestore(self, workspace, name, url, store_type="GeoTIFF"):
        """POST /rest/workspaces/{ws}/coveragestores.json — create a coverage store.

        Args:
            workspace: Target workspace name.
            name: Coverage store name.
            url: Path or URL to the raster data, e.g.
                ``"file:data/rasters/dem.tif"`` or ``"file:data/rasters/"``.
            store_type: Store type — ``"GeoTIFF"``, ``"WorldImage"``,
                ``"ImageMosaic"``, ``"NetCDF"``, ``"ImagePyramid"``.

        Example::

            client.create_coveragestore("nurc", "elevation",
                "file:data/rasters/dem.tif", store_type="GeoTIFF")
        """
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

    def update_coveragestore(self, workspace, name, *, description=None, enabled=None, url=None, **kwargs):
        """PUT /rest/workspaces/{ws}/coveragestores/{name}.json — update a coverage store.

        Args:
            workspace: Workspace name.
            name: Coverage store name.
            description: Human-readable description.
            enabled: Enable/disable the store.
            url: Update the raster data path/URL.
            **kwargs: Additional coverage store properties.

        Example::

            client.update_coveragestore("nurc", "dem", enabled=False)
        """
        payload = self._build_payload(
            {"description": description, "enabled": enabled, "url": url}, kwargs
        )
        self._put(f"workspaces/{workspace}/coveragestores/{name}.json", json={"coverageStore": payload})
        return {"workspace": workspace, "name": name, "updated": True}

    def delete_coveragestore(self, workspace, name, recurse=False):
        """DELETE /rest/workspaces/{ws}/coveragestores/{name} — delete a coverage store.

        Args:
            workspace: Workspace name.
            name: Coverage store name.
            recurse: If True, also delete all coverages and layers from this store.

        Example::

            client.delete_coveragestore("nurc", "old_dem", recurse=True)
        """
        self._delete(f"workspaces/{workspace}/coveragestores/{name}", params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # WMS STORES (cascaded WMS)
    # ═══════════════════════════════════════════════════════════════════════

    def list_wmsstores(self, workspace):
        """GET /rest/workspaces/{ws}/wmsstores.json — list cascaded WMS stores.

        Args:
            workspace: Workspace name.

        Example::

            stores = client.list_wmsstores("topp")
        """
        return self._list_helper(f"workspaces/{workspace}/wmsstores.json", "wmsStores", "wmsStore")

    def get_wmsstore(self, workspace, name):
        """GET /rest/workspaces/{ws}/wmsstores/{name}.json — get WMS store details.

        Args:
            workspace: Workspace name.
            name: WMS store name.

        Example::

            store = client.get_wmsstore("topp", "remote_wms")
            print(store["capabilitiesURL"])
        """
        return self._get(f"workspaces/{workspace}/wmsstores/{name}.json").json().get("wmsStore", {})

    def create_wmsstore(
        self, workspace, name, capabilities_url, *,
        enabled=None, max_connections=None, connect_timeout=None,
        read_timeout=None, **kwargs,
    ):
        """POST /rest/workspaces/{ws}/wmsstores.json — create a cascaded WMS store.

        Proxies a remote WMS service so its layers can be published locally.

        Args:
            workspace: Target workspace name.
            name: WMS store name.
            capabilities_url: GetCapabilities URL of the remote WMS, e.g.
                ``"https://example.com/geoserver/wms?service=WMS&version=1.1.1&request=GetCapabilities"``.
            enabled: Enable the store (default True).
            max_connections: Max concurrent connections to the remote WMS (default 6).
            connect_timeout: Connection timeout in seconds (default 30).
            read_timeout: Read timeout in seconds (default 60).
            **kwargs: Additional WMS store properties.

        Example::

            client.create_wmsstore("topp", "remote",
                "https://maps.example.com/wms?service=WMS&version=1.1.1&request=GetCapabilities",
                max_connections=10)
        """
        extras = self._build_payload(
            {"enabled": enabled, "maxConnections": max_connections,
             "connectTimeout": connect_timeout, "readTimeout": read_timeout},
            kwargs,
        )
        payload = {
            "wmsStore": {
                "name": name,
                "type": "WMS",
                "capabilitiesURL": capabilities_url,
                "workspace": {"name": workspace},
                "enabled": True,
                **extras,
            }
        }
        self._post(f"workspaces/{workspace}/wmsstores.json", json=payload)
        return {"workspace": workspace, "name": name, "created": True}

    def update_wmsstore(
        self, workspace, name, *,
        capabilities_url=None, enabled=None, max_connections=None,
        connect_timeout=None, read_timeout=None, description=None, **kwargs,
    ):
        """PUT /rest/workspaces/{ws}/wmsstores/{name}.json — update a WMS store.

        Args:
            workspace: Workspace name.
            name: WMS store name.
            capabilities_url: New GetCapabilities URL.
            enabled: Enable/disable the store.
            max_connections: Max concurrent connections.
            connect_timeout: Connection timeout in seconds.
            read_timeout: Read timeout in seconds.
            description: Human-readable description.
            **kwargs: Additional WMS store properties.

        Example::

            client.update_wmsstore("topp", "remote", enabled=False)
        """
        payload = self._build_payload(
            {"capabilitiesURL": capabilities_url, "enabled": enabled,
             "maxConnections": max_connections, "connectTimeout": connect_timeout,
             "readTimeout": read_timeout, "description": description},
            kwargs,
        )
        self._put(f"workspaces/{workspace}/wmsstores/{name}.json", json={"wmsStore": payload})
        return {"workspace": workspace, "name": name, "updated": True}

    def delete_wmsstore(self, workspace, name, recurse=False):
        """DELETE /rest/workspaces/{ws}/wmsstores/{name} — delete a WMS store.

        Args:
            workspace: Workspace name.
            name: WMS store name.
            recurse: If True, also delete all WMS layers from this store.

        Example::

            client.delete_wmsstore("topp", "old_wms", recurse=True)
        """
        self._delete(f"workspaces/{workspace}/wmsstores/{name}", params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # WMTS STORES (cascaded WMTS)
    # ═══════════════════════════════════════════════════════════════════════

    def list_wmtsstores(self, workspace):
        """GET /rest/workspaces/{ws}/wmtsstores.json — list cascaded WMTS stores.

        Args:
            workspace: Workspace name.

        Example::

            stores = client.list_wmtsstores("topp")
        """
        return self._list_helper(f"workspaces/{workspace}/wmtsstores.json", "wmtsStores", "wmtsStore")

    def get_wmtsstore(self, workspace, name):
        """GET /rest/workspaces/{ws}/wmtsstores/{name}.json — get WMTS store details.

        Args:
            workspace: Workspace name.
            name: WMTS store name.

        Example::

            store = client.get_wmtsstore("topp", "osm_tiles")
            print(store["capabilitiesURL"])
        """
        return self._get(f"workspaces/{workspace}/wmtsstores/{name}.json").json().get("wmtsStore", {})

    def create_wmtsstore(
        self, workspace, name, capabilities_url, *,
        enabled=None, max_connections=None, connect_timeout=None,
        read_timeout=None, **kwargs,
    ):
        """POST /rest/workspaces/{ws}/wmtsstores.json — create a cascaded WMTS store.

        Proxies a remote WMTS service so its tile layers can be published locally.

        Args:
            workspace: Target workspace name.
            name: WMTS store name.
            capabilities_url: GetCapabilities URL of the remote WMTS.
            enabled: Enable the store (default True).
            max_connections: Max concurrent connections to the remote WMTS.
            connect_timeout: Connection timeout in seconds.
            read_timeout: Read timeout in seconds.
            **kwargs: Additional WMTS store properties.

        Example::

            client.create_wmtsstore("topp", "osm_tiles",
                "https://tiles.example.com/wmts?request=GetCapabilities")
        """
        extras = self._build_payload(
            {"enabled": enabled, "maxConnections": max_connections,
             "connectTimeout": connect_timeout, "readTimeout": read_timeout},
            kwargs,
        )
        payload = {
            "wmtsStore": {
                "name": name,
                "type": "WMTS",
                "capabilitiesURL": capabilities_url,
                "workspace": {"name": workspace},
                "enabled": True,
                **extras,
            }
        }
        self._post(f"workspaces/{workspace}/wmtsstores.json", json=payload)
        return {"workspace": workspace, "name": name, "created": True}

    def update_wmtsstore(
        self, workspace, name, *,
        capabilities_url=None, enabled=None, max_connections=None,
        connect_timeout=None, read_timeout=None, description=None, **kwargs,
    ):
        """PUT /rest/workspaces/{ws}/wmtsstores/{name}.json — update a WMTS store.

        Args:
            workspace: Workspace name.
            name: WMTS store name.
            capabilities_url: New GetCapabilities URL.
            enabled: Enable/disable the store.
            max_connections: Max concurrent connections.
            connect_timeout: Connection timeout in seconds.
            read_timeout: Read timeout in seconds.
            description: Human-readable description.
            **kwargs: Additional WMTS store properties.

        Example::

            client.update_wmtsstore("topp", "osm_tiles", enabled=False)
        """
        payload = self._build_payload(
            {"capabilitiesURL": capabilities_url, "enabled": enabled,
             "maxConnections": max_connections, "connectTimeout": connect_timeout,
             "readTimeout": read_timeout, "description": description},
            kwargs,
        )
        self._put(f"workspaces/{workspace}/wmtsstores/{name}.json", json={"wmtsStore": payload})
        return {"workspace": workspace, "name": name, "updated": True}

    def delete_wmtsstore(self, workspace, name, recurse=False):
        """DELETE /rest/workspaces/{ws}/wmtsstores/{name} — delete a WMTS store.

        Args:
            workspace: Workspace name.
            name: WMTS store name.
            recurse: If True, also delete all WMTS layers from this store.

        Example::

            client.delete_wmtsstore("topp", "old_tiles", recurse=True)
        """
        self._delete(f"workspaces/{workspace}/wmtsstores/{name}", params={"recurse": "true"} if recurse else {})
        return {"workspace": workspace, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # FEATURE TYPES
    # ═══════════════════════════════════════════════════════════════════════

    def list_featuretypes(self, workspace, store=None):
        """GET /rest/workspaces/{ws}/[datastores/{ds}/]featuretypes.json — list feature types.

        Args:
            workspace: Workspace name.
            store: Optional data store name. If omitted, lists feature types
                across all stores in the workspace.

        Example::

            # All feature types in workspace
            fts = client.list_featuretypes("topp")

            # Only from a specific store
            fts = client.list_featuretypes("topp", store="pg_db")
        """
        if store:
            path = f"workspaces/{workspace}/datastores/{store}/featuretypes.json"
        else:
            path = f"workspaces/{workspace}/featuretypes.json"
        return self._list_helper(path, "featureTypes", "featureType")

    def get_featuretype(self, workspace, store, name):
        """GET /rest/.../featuretypes/{name}.json — get feature type details.

        Returns native CRS, bounding box, attributes, and publication settings.

        Args:
            workspace: Workspace name.
            store: Data store name.
            name: Feature type name.

        Example::

            ft = client.get_featuretype("topp", "pg_db", "roads")
            print(ft["srs"])        # e.g. "EPSG:4326"
            print(ft["nativeCRS"])  # full WKT or EPSG string
        """
        return (
            self._get(f"workspaces/{workspace}/datastores/{store}/featuretypes/{name}.json")
            .json()
            .get("featureType", {})
        )

    def create_featuretype(
        self, workspace, store, name, *,
        title=None, abstract=None, srs=None, native_crs=None,
        enabled=None, projection_policy=None, keywords=None,
        native_bounding_box=None, lat_lon_bounding_box=None,
        **kwargs,
    ):
        """POST /rest/.../featuretypes.json — publish a feature type from a data store.

        Creates a new feature type (and its associated layer) from an existing
        table/view in the data store.

        Args:
            workspace: Workspace name.
            store: Data store name.
            name: Feature type name (must match an existing table/view in the store,
                or use ``nativeName`` in kwargs if different).
            title: Human-readable title for the layer.
            abstract: Layer description/abstract.
            srs: Declared SRS, e.g. ``"EPSG:4326"`` or ``"EPSG:32632"``.
            native_crs: Native CRS of the data (usually auto-detected).
            enabled: Enable the feature type (default True).
            projection_policy: How to handle SRS mismatch —
                ``"FORCE_DECLARED"``, ``"REPROJECT_TO_DECLARED"``, or ``"NONE"``.
            keywords: Keyword list, e.g. ``{"string": ["roads", "infrastructure"]}``.
            native_bounding_box: Native extent dict with ``minx``, ``miny``,
                ``maxx``, ``maxy``, ``crs`` keys.
            lat_lon_bounding_box: Geographic extent dict (EPSG:4326).
            **kwargs: Additional feature type properties (e.g. ``nativeName``,
                ``maxFeatures``, ``numDecimals``).

        Example::

            # Publish a PostGIS table (auto-detects CRS and bounds)
            client.create_featuretype("topp", "pg_db", "roads",
                title="Road Network", srs="EPSG:4326")

            # Publish with different native name
            client.create_featuretype("topp", "pg_db", "my_roads",
                nativeName="road_segments", srs="EPSG:32632",
                projection_policy="REPROJECT_TO_DECLARED")
        """
        explicit = self._build_payload(
            {"title": title, "abstract": abstract, "srs": srs,
             "nativeCRS": native_crs, "enabled": enabled,
             "projectionPolicy": projection_policy, "keywords": keywords,
             "nativeBoundingBox": native_bounding_box,
             "latLonBoundingBox": lat_lon_bounding_box},
            kwargs,
        )
        self._post(
            f"workspaces/{workspace}/datastores/{store}/featuretypes.json",
            json={"featureType": {"name": name, **explicit}},
        )
        return {"workspace": workspace, "store": store, "name": name, "created": True}

    def update_featuretype(
        self, workspace, store, name, *,
        title=None, abstract=None, srs=None, enabled=None,
        projection_policy=None, keywords=None, advertised=None,
        native_bounding_box=None, lat_lon_bounding_box=None,
        **kwargs,
    ):
        """PUT /rest/.../featuretypes/{name}.json — update a feature type.

        Args:
            workspace: Workspace name.
            store: Data store name.
            name: Feature type name.
            title: Human-readable title.
            abstract: Layer description.
            srs: Declared SRS.
            enabled: Enable/disable the feature type.
            projection_policy: ``"FORCE_DECLARED"``, ``"REPROJECT_TO_DECLARED"``,
                or ``"NONE"``.
            keywords: Keyword list.
            advertised: Whether the layer appears in GetCapabilities.
            native_bounding_box: Native extent dict.
            lat_lon_bounding_box: Geographic extent dict.
            **kwargs: Additional feature type properties.

        Example::

            client.update_featuretype("topp", "pg_db", "roads", enabled=False)
            client.update_featuretype("topp", "pg_db", "roads",
                title="Updated Roads", abstract="Road network 2024")
        """
        payload = self._build_payload(
            {"title": title, "abstract": abstract, "srs": srs,
             "enabled": enabled, "projectionPolicy": projection_policy,
             "keywords": keywords, "advertised": advertised,
             "nativeBoundingBox": native_bounding_box,
             "latLonBoundingBox": lat_lon_bounding_box},
            kwargs,
        )
        self._put(f"workspaces/{workspace}/datastores/{store}/featuretypes/{name}.json", json={"featureType": payload})
        return {"workspace": workspace, "store": store, "name": name, "updated": True}

    def delete_featuretype(self, workspace, store, name, recurse=False):
        """DELETE /rest/.../featuretypes/{name} — delete a feature type.

        Args:
            workspace: Workspace name.
            store: Data store name.
            name: Feature type name.
            recurse: If True, also delete the associated layer.

        Example::

            client.delete_featuretype("topp", "pg_db", "old_roads", recurse=True)
        """
        self._delete(
            f"workspaces/{workspace}/datastores/{store}/featuretypes/{name}",
            params={"recurse": "true"} if recurse else {},
        )
        return {"workspace": workspace, "store": store, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # COVERAGES
    # ═══════════════════════════════════════════════════════════════════════

    def list_coverages(self, workspace, store=None):
        """GET /rest/workspaces/{ws}/[coveragestores/{cs}/]coverages.json — list coverages.

        Args:
            workspace: Workspace name.
            store: Optional coverage store name.

        Example::

            covs = client.list_coverages("nurc")
            covs = client.list_coverages("nurc", store="dem")
        """
        if store:
            path = f"workspaces/{workspace}/coveragestores/{store}/coverages.json"
        else:
            path = f"workspaces/{workspace}/coverages.json"
        return self._list_helper(path, "coverages", "coverage")

    def get_coverage(self, workspace, store, name):
        """GET /rest/.../coverages/{name}.json — get coverage details.

        Returns native format, CRS, dimensions, grid geometry, and bounding boxes.

        Args:
            workspace: Workspace name.
            store: Coverage store name.
            name: Coverage name.

        Example::

            cov = client.get_coverage("nurc", "dem", "DEM")
            print(cov["srs"], cov.get("nativeFormat", ""))
        """
        return (
            self._get(f"workspaces/{workspace}/coveragestores/{store}/coverages/{name}.json").json().get("coverage", {})
        )

    def create_coverage(
        self, workspace, store, name, *,
        title=None, abstract=None, srs=None, native_crs=None,
        enabled=None, native_format=None, projection_policy=None,
        native_bounding_box=None, lat_lon_bounding_box=None,
        **kwargs,
    ):
        """POST /rest/.../coverages.json — publish a coverage from a coverage store.

        Args:
            workspace: Workspace name.
            store: Coverage store name.
            name: Coverage name (must match the raster data source).
            title: Human-readable title.
            abstract: Coverage description.
            srs: Declared SRS, e.g. ``"EPSG:4326"``.
            native_crs: Native CRS (usually auto-detected).
            enabled: Enable the coverage (default True).
            native_format: Native raster format, e.g. ``"GeoTIFF"``, ``"NetCDF"``.
            projection_policy: ``"FORCE_DECLARED"``, ``"REPROJECT_TO_DECLARED"``,
                or ``"NONE"``.
            native_bounding_box: Native extent dict.
            lat_lon_bounding_box: Geographic extent dict.
            **kwargs: Additional coverage properties (e.g. ``dimensions``,
                ``interpolationMethods``, ``requestSRS``, ``responseSRS``).

        Example::

            client.create_coverage("nurc", "dem", "DEM",
                title="Digital Elevation Model", srs="EPSG:4326")
        """
        explicit = self._build_payload(
            {"title": title, "abstract": abstract, "srs": srs,
             "nativeCRS": native_crs, "enabled": enabled,
             "nativeFormat": native_format,
             "projectionPolicy": projection_policy,
             "nativeBoundingBox": native_bounding_box,
             "latLonBoundingBox": lat_lon_bounding_box},
            kwargs,
        )
        self._post(
            f"workspaces/{workspace}/coveragestores/{store}/coverages.json",
            json={"coverage": {"name": name, **explicit}},
        )
        return {"workspace": workspace, "store": store, "name": name, "created": True}

    def update_coverage(
        self, workspace, store, name, *,
        title=None, abstract=None, srs=None, enabled=None,
        projection_policy=None, advertised=None,
        native_bounding_box=None, lat_lon_bounding_box=None,
        **kwargs,
    ):
        """PUT /rest/.../coverages/{name}.json — update a coverage.

        Args:
            workspace: Workspace name.
            store: Coverage store name.
            name: Coverage name.
            title: Human-readable title.
            abstract: Coverage description.
            srs: Declared SRS.
            enabled: Enable/disable the coverage.
            projection_policy: ``"FORCE_DECLARED"``, ``"REPROJECT_TO_DECLARED"``,
                or ``"NONE"``.
            advertised: Whether the layer appears in GetCapabilities.
            native_bounding_box: Native extent dict.
            lat_lon_bounding_box: Geographic extent dict.
            **kwargs: Additional coverage properties.

        Example::

            client.update_coverage("nurc", "dem", "DEM", enabled=False)
        """
        payload = self._build_payload(
            {"title": title, "abstract": abstract, "srs": srs,
             "enabled": enabled, "projectionPolicy": projection_policy,
             "advertised": advertised,
             "nativeBoundingBox": native_bounding_box,
             "latLonBoundingBox": lat_lon_bounding_box},
            kwargs,
        )
        self._put(f"workspaces/{workspace}/coveragestores/{store}/coverages/{name}.json", json={"coverage": payload})
        return {"workspace": workspace, "store": store, "name": name, "updated": True}

    def delete_coverage(self, workspace, store, name, recurse=False):
        """DELETE /rest/.../coverages/{name} — delete a coverage.

        Args:
            workspace: Workspace name.
            store: Coverage store name.
            name: Coverage name.
            recurse: If True, also delete the associated layer.

        Example::

            client.delete_coverage("nurc", "dem", "DEM", recurse=True)
        """
        self._delete(
            f"workspaces/{workspace}/coveragestores/{store}/coverages/{name}",
            params={"recurse": "true"} if recurse else {},
        )
        return {"workspace": workspace, "store": store, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # WMS LAYERS (from cascaded WMS stores)
    # ═══════════════════════════════════════════════════════════════════════

    def list_wmslayers(self, workspace, store=None):
        """GET /rest/workspaces/{ws}/[wmsstores/{s}/]wmslayers.json — list cascaded WMS layers.

        Args:
            workspace: Workspace name.
            store: Optional WMS store name.

        Example::

            layers = client.list_wmslayers("topp", "remote_wms")
        """
        if store:
            path = f"workspaces/{workspace}/wmsstores/{store}/wmslayers.json"
        else:
            path = f"workspaces/{workspace}/wmslayers.json"
        return self._list_helper(path, "wmsLayers", "wmsLayer")

    def get_wmslayer(self, workspace, store, name):
        """GET /rest/.../wmslayers/{name}.json — get cascaded WMS layer details.

        Args:
            workspace: Workspace name.
            store: WMS store name.
            name: WMS layer name.

        Example::

            lyr = client.get_wmslayer("topp", "remote_wms", "remote_roads")
        """
        return self._get(f"workspaces/{workspace}/wmsstores/{store}/wmslayers/{name}.json").json().get("wmsLayer", {})

    def create_wmslayer(
        self, workspace, store, name, *,
        title=None, abstract=None, srs=None, enabled=None,
        native_bounding_box=None, lat_lon_bounding_box=None,
        **kwargs,
    ):
        """POST /rest/.../wmslayers.json — publish a layer from a cascaded WMS store.

        Args:
            workspace: Workspace name.
            store: WMS store name.
            name: Layer name on the remote WMS (must match a layer in the
                remote GetCapabilities).
            title: Local title for the published layer.
            abstract: Local description.
            srs: Declared SRS.
            enabled: Enable the layer (default True).
            native_bounding_box: Native extent dict.
            lat_lon_bounding_box: Geographic extent dict.
            **kwargs: Additional WMS layer properties.

        Example::

            client.create_wmslayer("topp", "remote_wms", "remote_roads",
                title="Roads (from remote WMS)", srs="EPSG:4326")
        """
        explicit = self._build_payload(
            {"title": title, "abstract": abstract, "srs": srs,
             "enabled": enabled, "nativeBoundingBox": native_bounding_box,
             "latLonBoundingBox": lat_lon_bounding_box},
            kwargs,
        )
        self._post(
            f"workspaces/{workspace}/wmsstores/{store}/wmslayers.json",
            json={"wmsLayer": {"name": name, **explicit}},
        )
        return {"workspace": workspace, "store": store, "name": name, "created": True}

    def update_wmslayer(
        self, workspace, store, name, *,
        title=None, abstract=None, srs=None, enabled=None, advertised=None,
        **kwargs,
    ):
        """PUT /rest/.../wmslayers/{name}.json — update a cascaded WMS layer.

        Args:
            workspace: Workspace name.
            store: WMS store name.
            name: WMS layer name.
            title: Human-readable title.
            abstract: Layer description.
            srs: Declared SRS.
            enabled: Enable/disable the layer.
            advertised: Whether the layer appears in GetCapabilities.
            **kwargs: Additional WMS layer properties.

        Example::

            client.update_wmslayer("topp", "remote_wms", "roads", enabled=False)
        """
        payload = self._build_payload(
            {"title": title, "abstract": abstract, "srs": srs,
             "enabled": enabled, "advertised": advertised},
            kwargs,
        )
        self._put(f"workspaces/{workspace}/wmsstores/{store}/wmslayers/{name}.json", json={"wmsLayer": payload})
        return {"workspace": workspace, "store": store, "name": name, "updated": True}

    def delete_wmslayer(self, workspace, store, name, recurse=False):
        """DELETE /rest/.../wmslayers/{name} — delete a cascaded WMS layer.

        Args:
            workspace: Workspace name.
            store: WMS store name.
            name: WMS layer name.
            recurse: If True, also delete the associated layer.

        Example::

            client.delete_wmslayer("topp", "remote_wms", "old_layer", recurse=True)
        """
        self._delete(
            f"workspaces/{workspace}/wmsstores/{store}/wmslayers/{name}", params={"recurse": "true"} if recurse else {}
        )
        return {"workspace": workspace, "store": store, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # WMTS LAYERS (from cascaded WMTS stores)
    # ═══════════════════════════════════════════════════════════════════════

    def list_wmtslayers(self, workspace, store=None):
        """GET /rest/workspaces/{ws}/[wmtsstores/{s}/]wmtslayers.json — list cascaded WMTS layers.

        Args:
            workspace: Workspace name.
            store: Optional WMTS store name.

        Example::

            layers = client.list_wmtslayers("topp", "osm_tiles")
        """
        if store:
            path = f"workspaces/{workspace}/wmtsstores/{store}/wmtslayers.json"
        else:
            path = f"workspaces/{workspace}/wmtslayers.json"
        return self._list_helper(path, "wmtsLayers", "wmtsLayer")

    def get_wmtslayer(self, workspace, store, name):
        """GET /rest/.../wmtslayers/{name}.json — get cascaded WMTS layer details.

        Args:
            workspace: Workspace name.
            store: WMTS store name.
            name: WMTS layer name.

        Example::

            lyr = client.get_wmtslayer("topp", "osm_tiles", "osm")
        """
        return (
            self._get(f"workspaces/{workspace}/wmtsstores/{store}/wmtslayers/{name}.json").json().get("wmtsLayer", {})
        )

    def create_wmtslayer(
        self, workspace, store, name, *,
        title=None, abstract=None, srs=None, enabled=None,
        native_bounding_box=None, lat_lon_bounding_box=None,
        **kwargs,
    ):
        """POST /rest/.../wmtslayers.json — publish a layer from a cascaded WMTS store.

        Args:
            workspace: Workspace name.
            store: WMTS store name.
            name: Layer identifier on the remote WMTS.
            title: Local title for the published layer.
            abstract: Local description.
            srs: Declared SRS.
            enabled: Enable the layer (default True).
            native_bounding_box: Native extent dict.
            lat_lon_bounding_box: Geographic extent dict.
            **kwargs: Additional WMTS layer properties.

        Example::

            client.create_wmtslayer("topp", "osm_tiles", "osm",
                title="OpenStreetMap Tiles", srs="EPSG:3857")
        """
        explicit = self._build_payload(
            {"title": title, "abstract": abstract, "srs": srs,
             "enabled": enabled, "nativeBoundingBox": native_bounding_box,
             "latLonBoundingBox": lat_lon_bounding_box},
            kwargs,
        )
        self._post(
            f"workspaces/{workspace}/wmtsstores/{store}/wmtslayers.json",
            json={"wmtsLayer": {"name": name, **explicit}},
        )
        return {"workspace": workspace, "store": store, "name": name, "created": True}

    def update_wmtslayer(
        self, workspace, store, name, *,
        title=None, abstract=None, srs=None, enabled=None, advertised=None,
        **kwargs,
    ):
        """PUT /rest/.../wmtslayers/{name}.json — update a cascaded WMTS layer.

        Args:
            workspace: Workspace name.
            store: WMTS store name.
            name: WMTS layer name.
            title: Human-readable title.
            abstract: Layer description.
            srs: Declared SRS.
            enabled: Enable/disable the layer.
            advertised: Whether the layer appears in GetCapabilities.
            **kwargs: Additional WMTS layer properties.

        Example::

            client.update_wmtslayer("topp", "osm_tiles", "osm", enabled=False)
        """
        payload = self._build_payload(
            {"title": title, "abstract": abstract, "srs": srs,
             "enabled": enabled, "advertised": advertised},
            kwargs,
        )
        self._put(f"workspaces/{workspace}/wmtsstores/{store}/wmtslayers/{name}.json", json={"wmtsLayer": payload})
        return {"workspace": workspace, "store": store, "name": name, "updated": True}

    def delete_wmtslayer(self, workspace, store, name, recurse=False):
        """DELETE /rest/.../wmtslayers/{name} — delete a cascaded WMTS layer.

        Args:
            workspace: Workspace name.
            store: WMTS store name.
            name: WMTS layer name.
            recurse: If True, also delete the associated layer.

        Example::

            client.delete_wmtslayer("topp", "osm_tiles", "old", recurse=True)
        """
        self._delete(
            f"workspaces/{workspace}/wmtsstores/{store}/wmtslayers/{name}",
            params={"recurse": "true"} if recurse else {},
        )
        return {"workspace": workspace, "store": store, "name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # LAYERS
    # ═══════════════════════════════════════════════════════════════════════

    def list_layers(self, workspace=None):
        """GET /rest/[workspaces/{ws}/]layers.json — list published layers.

        Args:
            workspace: Optional workspace name to scope the listing.

        Example::

            # All layers
            layers = client.list_layers()

            # Layers in a specific workspace
            layers = client.list_layers(workspace="topp")
        """
        path = f"workspaces/{workspace}/layers.json" if workspace else "layers.json"
        return self._list_helper(path, "layers", "layer")

    def get_layer(self, name, workspace=None):
        """GET /rest/[workspaces/{ws}/]layers/{name}.json — get layer details.

        Returns default style, available styles, resource reference, and
        publication settings.

        Args:
            name: Layer name.
            workspace: Optional workspace name.

        Example::

            lyr = client.get_layer("roads")
            print(lyr["defaultStyle"]["name"])  # e.g. "line"
        """
        path = f"workspaces/{workspace}/layers/{name}.json" if workspace else f"layers/{name}.json"
        return self._get(path).json().get("layer", {})

    def update_layer(
        self, name, workspace=None, *,
        default_style=None, enabled=None, queryable=None,
        opaque=None, advertised=None, **kwargs,
    ):
        """PUT /rest/[workspaces/{ws}/]layers/{name}.json — update layer properties.

        Args:
            name: Layer name.
            workspace: Optional workspace name.
            default_style: Default style name or dict ``{"name": "style_name"}``.
                This is the style used when no ``STYLES`` param is in the WMS request.
            enabled: Enable/disable the layer.
            queryable: Whether the layer supports GetFeatureInfo (WMS).
            opaque: Whether the layer is opaque (WMS).
            advertised: Whether the layer appears in GetCapabilities.
            **kwargs: Additional layer properties (e.g. ``attribution``,
                ``styles`` for additional styles list).

        Example::

            client.update_layer("roads", enabled=False)
            client.update_layer("roads",
                default_style={"name": "road_style"},
                queryable=True)
        """
        explicit = {}
        if default_style is not None:
            explicit["defaultStyle"] = (
                default_style if isinstance(default_style, dict) else {"name": default_style}
            )
        if enabled is not None:
            explicit["enabled"] = enabled
        if queryable is not None:
            explicit["queryable"] = queryable
        if opaque is not None:
            explicit["opaque"] = opaque
        if advertised is not None:
            explicit["advertised"] = advertised
        explicit.update(kwargs)
        path = f"workspaces/{workspace}/layers/{name}.json" if workspace else f"layers/{name}.json"
        self._put(path, json={"layer": explicit})
        return {"name": name, "updated": True}

    def delete_layer(self, name, workspace=None, recurse=False):
        """DELETE /rest/[workspaces/{ws}/]layers/{name} — delete a layer.

        Args:
            name: Layer name.
            workspace: Optional workspace name.
            recurse: If True, also delete the underlying resource
                (feature type or coverage).

        Example::

            client.delete_layer("old_roads", recurse=True)
        """
        path = f"workspaces/{workspace}/layers/{name}" if workspace else f"layers/{name}"
        self._delete(path, params={"recurse": "true"} if recurse else {})
        return {"name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER GROUPS
    # ═══════════════════════════════════════════════════════════════════════

    def list_layergroups(self, workspace=None):
        """GET /rest/[workspaces/{ws}/]layergroups.json — list layer groups.

        Args:
            workspace: Optional workspace name to scope the listing.

        Example::

            groups = client.list_layergroups()
            groups = client.list_layergroups(workspace="topp")
        """
        path = f"workspaces/{workspace}/layergroups.json" if workspace else "layergroups.json"
        return self._list_helper(path, "layerGroups", "layerGroup")

    def get_layergroup(self, name, workspace=None):
        """GET /rest/[workspaces/{ws}/]layergroups/{name}.json — get layer group details.

        Args:
            name: Layer group name.
            workspace: Optional workspace name.

        Example::

            lg = client.get_layergroup("spearfish")
            for pub in lg["publishables"]["published"]:
                print(pub["name"])
        """
        path = f"workspaces/{workspace}/layergroups/{name}.json" if workspace else f"layergroups/{name}.json"
        return self._get(path).json().get("layerGroup", {})

    def create_layergroup(
        self, name, layers, workspace=None, *,
        title=None, abstract_txt=None, mode=None, bounds=None,
        **kwargs,
    ):
        """POST /rest/[workspaces/{ws}/]layergroups.json — create a layer group.

        Args:
            name: Layer group name.
            layers: List of layer names to include, e.g.
                ``["topp:roads", "topp:rivers"]``.
            workspace: Optional workspace to scope the group.
            title: Human-readable title.
            abstract_txt: Group description (key is ``abstractTxt`` in the REST API).
            mode: Group mode — ``"SINGLE"`` (default, merged into one layer),
                ``"NAMED"`` (each layer individually accessible),
                ``"CONTAINER"`` (not directly renderable, just a grouping),
                ``"EO"`` (Earth Observation).
            bounds: Bounding box dict with ``minx``, ``miny``, ``maxx``, ``maxy``,
                ``crs`` keys.
            **kwargs: Additional layer group properties (e.g. ``styles``).

        Example::

            client.create_layergroup("city_map",
                ["topp:roads", "topp:buildings", "topp:parks"],
                workspace="topp",
                title="City Overview Map",
                mode="NAMED")
        """
        path = f"workspaces/{workspace}/layergroups.json" if workspace else "layergroups.json"
        published = [{"@type": "layer", "name": lyr} for lyr in layers]
        explicit = self._build_payload(
            {"title": title, "abstractTxt": abstract_txt, "mode": mode, "bounds": bounds},
            kwargs,
        )
        self._post(path, json={"layerGroup": {"name": name, "layers": {"published": published}, **explicit}})
        return {"name": name, "created": True}

    def update_layergroup(
        self, name, workspace=None, *,
        title=None, abstract_txt=None, mode=None, bounds=None,
        **kwargs,
    ):
        """PUT /rest/[workspaces/{ws}/]layergroups/{name}.json — update a layer group.

        Args:
            name: Layer group name.
            workspace: Optional workspace name.
            title: Human-readable title.
            abstract_txt: Group description.
            mode: Group mode (``"SINGLE"``, ``"NAMED"``, ``"CONTAINER"``, ``"EO"``).
            bounds: Bounding box dict.
            **kwargs: Additional layer group properties (e.g. ``layers``,
                ``styles`` for full replacement).

        Example::

            client.update_layergroup("spearfish", title="Updated Group")
        """
        payload = self._build_payload(
            {"title": title, "abstractTxt": abstract_txt, "mode": mode, "bounds": bounds},
            kwargs,
        )
        path = f"workspaces/{workspace}/layergroups/{name}.json" if workspace else f"layergroups/{name}.json"
        self._put(path, json={"layerGroup": payload})
        return {"name": name, "updated": True}

    def delete_layergroup(self, name, workspace=None):
        """DELETE /rest/[workspaces/{ws}/]layergroups/{name} — delete a layer group.

        Does not delete the individual layers — only the group definition.

        Args:
            name: Layer group name.
            workspace: Optional workspace name.

        Example::

            client.delete_layergroup("old_group")
        """
        path = f"workspaces/{workspace}/layergroups/{name}" if workspace else f"layergroups/{name}"
        self._delete(path)
        return {"name": name, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # STYLES
    # ═══════════════════════════════════════════════════════════════════════

    def list_styles(self, workspace=None):
        """GET /rest/[workspaces/{ws}/]styles.json — list available styles.

        Args:
            workspace: Optional workspace name. If omitted, lists global styles.

        Example::

            styles = client.list_styles()
            styles = client.list_styles(workspace="topp")
        """
        path = f"workspaces/{workspace}/styles.json" if workspace else "styles.json"
        return self._list_helper(path, "styles", "style")

    def get_style(self, name, workspace=None):
        """GET /rest/[workspaces/{ws}/]styles/{name}.json — get style metadata.

        Returns format, version, filename, and language version.

        Args:
            name: Style name.
            workspace: Optional workspace name.

        Example::

            style = client.get_style("line")
            print(style["format"])  # e.g. "sld"
        """
        path = f"workspaces/{workspace}/styles/{name}.json" if workspace else f"styles/{name}.json"
        return self._get(path).json().get("style", {})

    def get_style_body(self, name, workspace=None):
        """GET /rest/[workspaces/{ws}/]styles/{name}.sld — get the SLD/CSS body.

        Returns the raw SLD XML or CSS text of a style definition.

        Args:
            name: Style name.
            workspace: Optional workspace name.

        Example::

            sld_xml = client.get_style_body("line")
            print(sld_xml[:100])  # SLD XML content
        """
        path = f"workspaces/{workspace}/styles/{name}.sld" if workspace else f"styles/{name}.sld"
        return self._request("GET", path, headers={"Accept": "application/vnd.ogc.sld+xml"}).text

    def create_style(self, name, sld_body, workspace=None):
        """Create a new style with an SLD body.

        Two-step process: (1) register the style name, (2) upload the SLD body.

        Args:
            name: Style name (also used as ``{name}.sld`` filename).
            sld_body: SLD XML string. Minimal valid SLD::

                <?xml version="1.0" encoding="UTF-8"?>
                <StyledLayerDescriptor version="1.0.0"
                  xsi:schemaLocation="http://www.opengis.net/sld ..."
                  xmlns="http://www.opengis.net/sld"
                  xmlns:ogc="http://www.opengis.net/ogc"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                  <NamedLayer><Name>my_style</Name>
                    <UserStyle><Title>My Style</Title>
                      <FeatureTypeStyle>
                        <Rule><LineSymbolizer><Stroke>
                          <CssParameter name="stroke">#0000FF</CssParameter>
                        </Stroke></LineSymbolizer></Rule>
                      </FeatureTypeStyle>
                    </UserStyle>
                  </NamedLayer>
                </StyledLayerDescriptor>

            workspace: Optional workspace to scope the style.

        Example::

            client.create_style("blue_line", sld_xml, workspace="topp")
        """
        path = f"workspaces/{workspace}/styles" if workspace else "styles"
        self._post(f"{path}.json", json={"style": {"name": name, "filename": f"{name}.sld"}})
        self._request(
            "PUT",
            f"{path}/{name}",
            data=sld_body.encode("utf-8"),
            headers={"Content-Type": "application/vnd.ogc.sld+xml"},
        )
        return {"name": name, "created": True}

    def update_style(self, name, sld_body, workspace=None):
        """PUT /rest/[workspaces/{ws}/]styles/{name} — re-upload the SLD body.

        Replaces the entire style definition with the new SLD XML.

        Args:
            name: Style name.
            sld_body: New SLD XML string.
            workspace: Optional workspace name.

        Example::

            client.update_style("line", new_sld_xml)
        """
        path = f"workspaces/{workspace}/styles/{name}" if workspace else f"styles/{name}"
        self._request(
            "PUT", path, data=sld_body.encode("utf-8"), headers={"Content-Type": "application/vnd.ogc.sld+xml"}
        )
        return {"name": name, "updated": True}

    def delete_style(self, name, workspace=None, purge=False):
        """DELETE /rest/[workspaces/{ws}/]styles/{name} — delete a style.

        Args:
            name: Style name.
            workspace: Optional workspace name.
            purge: If True, also delete the underlying SLD file from the
                data directory.

        Example::

            client.delete_style("old_style", purge=True)
        """
        path = f"workspaces/{workspace}/styles/{name}" if workspace else f"styles/{name}"
        self._delete(path, params={"purge": "true"} if purge else {})
        return {"name": name, "deleted": True}

    def list_layer_styles(self, layer_name):
        """GET /rest/layers/{layer}/styles.json — list styles associated with a layer.

        Args:
            layer_name: Layer name.

        Example::

            styles = client.list_layer_styles("roads")
        """
        return self._list_helper(f"layers/{layer_name}/styles.json", "styles", "style")

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE SETTINGS (WMS / WFS / WCS / WMTS)
    # ═══════════════════════════════════════════════════════════════════════

    def get_service_settings(self, service, workspace=None):
        """GET /rest/services/{svc}/[workspaces/{ws}/]settings.json — get OGC service settings.

        Args:
            service: Service type — ``"wms"``, ``"wfs"``, ``"wcs"``, or ``"wmts"``.
            workspace: Optional workspace for workspace-specific overrides.

        Example::

            wms = client.get_service_settings("wms")
            print(wms["wms"]["enabled"])
        """
        svc = service.lower()
        path = f"services/{svc}/workspaces/{workspace}/settings.json" if workspace else f"services/{svc}/settings.json"
        return self._get(path).json()

    def update_service_settings(
        self, service, workspace=None, *,
        enabled=None, title=None, abstract=None, maintainer=None,
        online_resource=None, fees=None, access_constraints=None,
        cite_compliant=None, max_features=None, schema_base_url=None,
        **kwargs,
    ):
        """PUT /rest/services/{svc}/[workspaces/{ws}/]settings.json — update OGC service settings.

        Args:
            service: Service type — ``"wms"``, ``"wfs"``, ``"wcs"``, or ``"wmts"``.
            workspace: Optional workspace for workspace-specific overrides.
            enabled: Enable/disable the service.
            title: Service title shown in GetCapabilities.
            abstract: Service description.
            maintainer: Maintainer name.
            online_resource: Service online resource URL.
            fees: Fee information string (e.g. ``"NONE"``).
            access_constraints: Access constraint string (e.g. ``"NONE"``).
            cite_compliant: Enable strict OGC CITE compliance.
            max_features: WFS-specific: max features per GetFeature response.
            schema_base_url: Base URL for schema references.
            **kwargs: Additional service-specific properties (e.g.
                ``watermark`` for WMS, ``srs`` list for WFS).

        Example::

            client.update_service_settings("wms",
                title="My WMS Service", enabled=True)
            client.update_service_settings("wfs",
                max_features=10000, cite_compliant=False)
        """
        payload = self._build_payload(
            {"enabled": enabled, "title": title, "abstrct": abstract,
             "maintainer": maintainer, "onlineResource": online_resource,
             "fees": fees, "accessConstraints": access_constraints,
             "citeCompliant": cite_compliant, "maxFeatures": max_features,
             "schemaBaseURL": schema_base_url},
            kwargs,
        )
        svc = service.lower()
        path = f"services/{svc}/workspaces/{workspace}/settings.json" if workspace else f"services/{svc}/settings.json"
        self._put(path, json={svc: payload})
        return {"service": service, "updated": True}

    # ═══════════════════════════════════════════════════════════════════════
    # GLOBAL SETTINGS
    # ═══════════════════════════════════════════════════════════════════════

    def get_settings(self):
        """GET /rest/settings.json — get global GeoServer settings.

        Returns proxy base URL, charset, number of decimals, verbose
        exceptions, and other global configuration.

        Example::

            settings = client.get_settings()
            print(settings["global"]["settings"]["charset"])  # e.g. "UTF-8"
        """
        return self._get("settings.json").json()

    def update_settings(
        self, *,
        verbose=None, verbose_exceptions=None, num_decimals=None,
        charset=None, online_resource=None, proxy_base_url=None,
        **kwargs,
    ):
        """PUT /rest/settings.json — update global GeoServer settings.

        Args:
            verbose: Enable verbose output in responses.
            verbose_exceptions: Include full stack traces in error responses.
            num_decimals: Number of decimal places in coordinate output.
            charset: Output character set, e.g. ``"UTF-8"``.
            online_resource: Global online resource URL.
            proxy_base_url: Proxy base URL for generated URLs (important when
                behind a reverse proxy), e.g. ``"https://maps.example.com/geoserver"``.
            **kwargs: Additional global settings properties.

        Example::

            client.update_settings(
                proxy_base_url="https://maps.example.com/geoserver",
                num_decimals=8)
        """
        payload = self._build_payload(
            {"verbose": verbose, "verboseExceptions": verbose_exceptions,
             "numDecimals": num_decimals, "charset": charset,
             "onlineResource": online_resource, "proxyBaseUrl": proxy_base_url},
            kwargs,
        )
        self._put("settings.json", json={"global": payload})
        return {"updated": True}

    def get_contact(self):
        """GET /rest/settings/contact.json — get contact information.

        Example::

            contact = client.get_contact()
            print(contact["contact"]["contactPerson"])
        """
        return self._get("settings/contact.json").json()

    def update_contact(
        self, *,
        contact_person=None, contact_organization=None, contact_position=None,
        contact_email=None, contact_phone=None, contact_fax=None,
        address=None, address_type=None, address_city=None,
        address_state=None, address_postal_code=None, address_country=None,
        **kwargs,
    ):
        """PUT /rest/settings/contact.json — update contact information.

        Shown in OGC GetCapabilities responses.

        Args:
            contact_person: Contact person name.
            contact_organization: Organization name.
            contact_position: Contact position/title.
            contact_email: Email address.
            contact_phone: Phone number.
            contact_fax: Fax number.
            address: Street address.
            address_type: Address type (e.g. ``"work"``).
            address_city: City.
            address_state: State/province.
            address_postal_code: Postal/ZIP code.
            address_country: Country.
            **kwargs: Additional contact properties.

        Example::

            client.update_contact(
                contact_person="Admin",
                contact_organization="ACME Corp",
                contact_email="admin@example.com")
        """
        payload = self._build_payload(
            {"contactPerson": contact_person, "contactOrganization": contact_organization,
             "contactPosition": contact_position, "contactEmail": contact_email,
             "contactVoice": contact_phone, "contactFacsimile": contact_fax,
             "address": address, "addressType": address_type,
             "addressCity": address_city, "addressState": address_state,
             "addressPostalCode": address_postal_code, "addressCountry": address_country},
            kwargs,
        )
        self._put("settings/contact.json", json={"contact": payload})
        return {"updated": True}

    # ── Local workspace settings ──

    def get_local_settings(self, workspace):
        """GET /rest/workspaces/{ws}/settings.json — get workspace-specific settings.

        Args:
            workspace: Workspace name.

        Example::

            settings = client.get_local_settings("topp")
        """
        return self._get(f"workspaces/{workspace}/settings.json").json()

    def create_local_settings(
        self, workspace, *,
        charset=None, num_decimals=None, verbose=None,
        verbose_exceptions=None, **kwargs,
    ):
        """POST /rest/workspaces/{ws}/settings.json — create workspace-specific settings.

        Overrides global settings for this workspace's virtual OGC services.

        Args:
            workspace: Workspace name.
            charset: Output character set override.
            num_decimals: Decimal places override.
            verbose: Verbose output override.
            verbose_exceptions: Verbose exceptions override.
            **kwargs: Additional settings properties.

        Example::

            client.create_local_settings("topp", num_decimals=4, charset="UTF-8")
        """
        payload = self._build_payload(
            {"charset": charset, "numDecimals": num_decimals,
             "verbose": verbose, "verboseExceptions": verbose_exceptions},
            kwargs,
        )
        self._post(f"workspaces/{workspace}/settings.json", json={"settings": payload})
        return {"workspace": workspace, "created": True}

    def update_local_settings(
        self, workspace, *,
        charset=None, num_decimals=None, verbose=None,
        verbose_exceptions=None, **kwargs,
    ):
        """PUT /rest/workspaces/{ws}/settings.json — update workspace-specific settings.

        Args:
            workspace: Workspace name.
            charset: Output character set override.
            num_decimals: Decimal places override.
            verbose: Verbose output override.
            verbose_exceptions: Verbose exceptions override.
            **kwargs: Additional settings properties.

        Example::

            client.update_local_settings("topp", num_decimals=6)
        """
        payload = self._build_payload(
            {"charset": charset, "numDecimals": num_decimals,
             "verbose": verbose, "verboseExceptions": verbose_exceptions},
            kwargs,
        )
        self._put(f"workspaces/{workspace}/settings.json", json={"settings": payload})
        return {"workspace": workspace, "updated": True}

    def delete_local_settings(self, workspace):
        """DELETE /rest/workspaces/{ws}/settings.json — remove workspace-specific settings.

        Reverts to global settings for this workspace.

        Args:
            workspace: Workspace name.

        Example::

            client.delete_local_settings("topp")
        """
        self._delete(f"workspaces/{workspace}/settings.json")
        return {"workspace": workspace, "deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # LOGGING
    # ═══════════════════════════════════════════════════════════════════════

    def get_logging(self):
        """GET /rest/logging.json — get GeoServer logging configuration.

        Example::

            logging = client.get_logging()
            print(logging["logging"]["level"])  # e.g. "DEFAULT_LOGGING.properties"
        """
        return self._get("logging.json").json()

    def update_logging(self, *, level=None, location=None, std_out_logging=None, **kwargs):
        """PUT /rest/logging.json — update logging configuration.

        Args:
            level: Logging profile — ``"DEFAULT_LOGGING.properties"``,
                ``"PRODUCTION_LOGGING.properties"``,
                ``"VERBOSE_LOGGING.properties"``,
                ``"GEOTOOLS_DEVELOPER_LOGGING.properties"``,
                ``"GEOSERVER_DEVELOPER_LOGGING.properties"``.
            location: Log file path relative to data directory, e.g.
                ``"logs/geoserver.log"``.
            std_out_logging: Also log to stdout.
            **kwargs: Additional logging properties.

        Example::

            client.update_logging(
                level="PRODUCTION_LOGGING.properties",
                std_out_logging=True)
        """
        payload = self._build_payload(
            {"level": level, "location": location, "stdOutLogging": std_out_logging},
            kwargs,
        )
        self._put("logging.json", json={"logging": payload})
        return {"updated": True}

    # ═══════════════════════════════════════════════════════════════════════
    # FONTS
    # ═══════════════════════════════════════════════════════════════════════

    def list_fonts(self):
        """GET /rest/fonts.json — list fonts available for SLD styling.

        Returns a list of font family names installed on the GeoServer JVM.

        Example::

            fonts = client.list_fonts()
            for name in fonts.get("fonts", []):
                print(name)
        """
        return self._get("fonts.json").json()

    # ═══════════════════════════════════════════════════════════════════════
    # TEMPLATES (Freemarker)
    # ═══════════════════════════════════════════════════════════════════════

    def list_templates(self, workspace=None, store=None, featuretype=None):
        """GET /rest/[...]/templates.json — list Freemarker templates.

        Templates can be scoped at global, workspace, store, or feature type level.

        Args:
            workspace: Optional workspace name.
            store: Optional data store name (requires workspace).
            featuretype: Optional feature type name (requires workspace and store).

        Example::

            templates = client.list_templates(workspace="topp")
        """
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
        """GET /rest/[...]/templates/{name} — get a Freemarker template body.

        Args:
            name: Template filename, e.g. ``"header.ftl"``.
            workspace: Optional workspace name.
            store: Optional data store name.
            featuretype: Optional feature type name.

        Example::

            body = client.get_template("header.ftl", workspace="topp")
        """
        base = self._template_path(workspace, store, featuretype)
        resp = self._request("GET", f"{base}/{name}", headers={"Accept": "text/plain"})
        return resp.text

    def create_template(self, name, body, workspace=None, store=None, featuretype=None):
        """PUT /rest/[...]/templates/{name} — upload a Freemarker template.

        Templates customize GetFeatureInfo HTML output. Common template names:
        ``header.ftl``, ``content.ftl``, ``footer.ftl``.

        Args:
            name: Template filename.
            body: Freemarker template content string.
            workspace: Optional workspace scope.
            store: Optional store scope.
            featuretype: Optional feature type scope.

        Example::

            client.create_template("header.ftl",
                "<html><body><h1>${type.name}</h1>",
                workspace="topp")
        """
        base = self._template_path(workspace, store, featuretype)
        self._request("PUT", f"{base}/{name}", data=body.encode("utf-8"), headers={"Content-Type": "text/plain"})
        return {"name": name, "created": True}

    def delete_template(self, name, workspace=None, store=None, featuretype=None):
        """DELETE /rest/[...]/templates/{name} — delete a Freemarker template.

        Args:
            name: Template filename.
            workspace: Optional workspace scope.
            store: Optional store scope.
            featuretype: Optional feature type scope.

        Example::

            client.delete_template("header.ftl", workspace="topp")
        """
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
        """GET /rest/resource/{path} — get file content from the data directory.

        Returns JSON for directories, raw bytes for files.

        Args:
            path: Resource path relative to data directory, e.g.
                ``"styles/my_style.sld"`` or ``"workspaces/topp"``.

        Example::

            content = client.get_resource("styles/line.sld")
        """
        resp = self._get(f"resource/{path}")
        content_type = resp.headers.get("Content-Type", "")
        if "json" in content_type:
            return resp.json()
        return resp.content

    def get_resource_metadata(self, path):
        """HEAD /rest/resource/{path} — get resource metadata (type, size, modified date).

        Args:
            path: Resource path.

        Example::

            meta = client.get_resource_metadata("styles/line.sld")
            print(meta["resource-type"])  # "file" or "directory"
        """
        resp = self._request("HEAD", f"resource/{path}")
        return {
            "content-type": resp.headers.get("Content-Type"),
            "content-length": resp.headers.get("Content-Length"),
            "last-modified": resp.headers.get("Last-Modified"),
            "resource-type": resp.headers.get("Resource-Type"),
        }

    def put_resource(self, path, data, content_type="application/octet-stream"):
        """PUT /rest/resource/{path} — upload or replace a file in the data directory.

        Args:
            path: Target path.
            data: File content as bytes.
            content_type: MIME type, e.g. ``"application/xml"`` for SLD files.

        Example::

            client.put_resource("styles/custom.sld",
                b"<sld>...</sld>", "application/xml")
        """
        self._request("PUT", f"resource/{path}", data=data, headers={"Content-Type": content_type})
        return {"path": path, "uploaded": True}

    def delete_resource(self, path):
        """DELETE /rest/resource/{path} — delete a file from the data directory.

        Args:
            path: Resource path to delete.

        Example::

            client.delete_resource("styles/old.sld")
        """
        self._delete(f"resource/{path}")
        return {"path": path, "deleted": True}

    def list_resource_directory(self, path=""):
        """GET /rest/resource/{path}.json — list directory contents.

        Args:
            path: Directory path (empty string for root).

        Example::

            listing = client.list_resource_directory("styles")
        """
        resp = self._get(f"resource/{path}.json" if path else "resource.json")
        return resp.json()

    # ═══════════════════════════════════════════════════════════════════════
    # SECURITY — USERS
    # ═══════════════════════════════════════════════════════════════════════

    def list_users(self, service="default"):
        """GET /rest/security/usergroup/service/{svc}/users.json — list users.

        Args:
            service: User/group service name (default ``"default"``).

        Example::

            users = client.list_users()
        """
        return self._get(f"security/usergroup/service/{service}/users.json").json()

    def get_user(self, username, service="default"):
        """GET /rest/security/usergroup/service/{svc}/user/{name}.json — get user details.

        Args:
            username: Username.
            service: User/group service name.

        Example::

            user = client.get_user("admin")
            print(user["user"]["enabled"])
        """
        return self._get(f"security/usergroup/service/{service}/user/{username}.json").json()

    def create_user(self, username, password, enabled=True, service="default"):
        """POST /rest/security/usergroup/service/{svc}/users.json — create a user.

        Args:
            username: New username.
            password: User password.
            enabled: Whether the user is enabled (default True).
            service: User/group service name.

        Example::

            client.create_user("editor", "secure_pass_123")
            client.create_user("viewer", "pass", enabled=False)
        """
        payload = {"user": {"userName": username, "password": password, "enabled": enabled}}
        self._post(f"security/usergroup/service/{service}/users.json", json=payload)
        return {"username": username, "created": True}

    def update_user(self, username, service="default", *, password=None, enabled=None, **kwargs):
        """PUT /rest/security/usergroup/service/{svc}/user/{name}.json — update a user.

        Args:
            username: Username to update.
            service: User/group service name.
            password: New password.
            enabled: Enable/disable the user.
            **kwargs: Additional user properties.

        Example::

            client.update_user("editor", password="new_pass")
            client.update_user("editor", enabled=False)
        """
        payload = self._build_payload({"password": password, "enabled": enabled}, kwargs)
        self._put(f"security/usergroup/service/{service}/user/{username}.json", json={"user": payload})
        return {"username": username, "updated": True}

    def delete_user(self, username, service="default"):
        """DELETE /rest/security/usergroup/service/{svc}/user/{name} — delete a user.

        Args:
            username: Username to delete.
            service: User/group service name.

        Example::

            client.delete_user("old_editor")
        """
        self._delete(f"security/usergroup/service/{service}/user/{username}")
        return {"username": username, "deleted": True}

    # ── User groups ──

    def list_user_groups(self, service="default"):
        """GET /rest/security/usergroup/service/{svc}/groups.json — list user groups.

        Args:
            service: User/group service name.

        Example::

            groups = client.list_user_groups()
        """
        return self._get(f"security/usergroup/service/{service}/groups.json").json()

    def create_user_group(self, group_name, service="default"):
        """POST /rest/security/usergroup/service/{svc}/group/{name} — create a user group.

        Args:
            group_name: Group name.
            service: User/group service name.

        Example::

            client.create_user_group("editors")
        """
        self._post(f"security/usergroup/service/{service}/group/{group_name}")
        return {"group": group_name, "created": True}

    def delete_user_group(self, group_name, service="default"):
        """DELETE /rest/security/usergroup/service/{svc}/group/{name} — delete a user group.

        Args:
            group_name: Group name.
            service: User/group service name.

        Example::

            client.delete_user_group("old_group")
        """
        self._delete(f"security/usergroup/service/{service}/group/{group_name}")
        return {"group": group_name, "deleted": True}

    def add_user_to_group(self, username, group_name, service="default"):
        """POST /.../user/{name}/group/{group} — add a user to a group.

        Args:
            username: Username to add.
            group_name: Target group.
            service: User/group service name.

        Example::

            client.add_user_to_group("editor", "editors")
        """
        self._post(f"security/usergroup/service/{service}/user/{username}/group/{group_name}")
        return {"username": username, "group": group_name, "added": True}

    def remove_user_from_group(self, username, group_name, service="default"):
        """DELETE /.../user/{name}/group/{group} — remove a user from a group.

        Args:
            username: Username to remove.
            group_name: Group to remove from.
            service: User/group service name.

        Example::

            client.remove_user_from_group("editor", "editors")
        """
        self._delete(f"security/usergroup/service/{service}/user/{username}/group/{group_name}")
        return {"username": username, "group": group_name, "removed": True}

    def list_usergroup_services(self):
        """GET /rest/security/usergroup/services.json — list available user/group services.

        Example::

            services = client.list_usergroup_services()
        """
        return self._get("security/usergroup/services.json").json()

    # ═══════════════════════════════════════════════════════════════════════
    # SECURITY — ROLES
    # ═══════════════════════════════════════════════════════════════════════

    def list_roles(self):
        """GET /rest/security/roles.json — list all roles.

        Built-in roles: ``ROLE_ADMIN``, ``ROLE_AUTHENTICATED``, ``ROLE_ANONYMOUS``.

        Example::

            roles = client.list_roles()
        """
        return self._get("security/roles.json").json()

    def list_roles_for_user(self, username):
        """GET /rest/security/roles/user/{name}.json — list roles for a user.

        Args:
            username: Username.

        Example::

            roles = client.list_roles_for_user("admin")
        """
        return self._get(f"security/roles/user/{username}.json").json()

    def list_roles_for_group(self, group_name):
        """GET /rest/security/roles/group/{name}.json — list roles for a group.

        Args:
            group_name: Group name.

        Example::

            roles = client.list_roles_for_group("editors")
        """
        return self._get(f"security/roles/group/{group_name}.json").json()

    def create_role(self, role_name):
        """POST /rest/security/roles/role/{name} — create a new role.

        Convention: role names are uppercase with ``ROLE_`` prefix,
        e.g. ``"ROLE_EDITOR"``, ``"ROLE_DATA_ADMIN"``.

        Args:
            role_name: Role name.

        Example::

            client.create_role("ROLE_EDITOR")
        """
        self._post(f"security/roles/role/{role_name}")
        return {"role": role_name, "created": True}

    def delete_role(self, role_name):
        """DELETE /rest/security/roles/role/{name} — delete a role.

        Args:
            role_name: Role name.

        Example::

            client.delete_role("ROLE_EDITOR")
        """
        self._delete(f"security/roles/role/{role_name}")
        return {"role": role_name, "deleted": True}

    def assign_role_to_user(self, role_name, username):
        """POST /rest/security/roles/role/{role}/user/{name} — assign a role to a user.

        Args:
            role_name: Role name.
            username: Username.

        Example::

            client.assign_role_to_user("ROLE_EDITOR", "editor1")
        """
        self._post(f"security/roles/role/{role_name}/user/{username}")
        return {"role": role_name, "username": username, "assigned": True}

    def remove_role_from_user(self, role_name, username):
        """DELETE /rest/security/roles/role/{role}/user/{name} — remove a role from a user.

        Args:
            role_name: Role name.
            username: Username.

        Example::

            client.remove_role_from_user("ROLE_EDITOR", "editor1")
        """
        self._delete(f"security/roles/role/{role_name}/user/{username}")
        return {"role": role_name, "username": username, "removed": True}

    def assign_role_to_group(self, role_name, group_name):
        """POST /rest/security/roles/role/{role}/group/{name} — assign a role to a group.

        Args:
            role_name: Role name.
            group_name: Group name.

        Example::

            client.assign_role_to_group("ROLE_EDITOR", "editors")
        """
        self._post(f"security/roles/role/{role_name}/group/{group_name}")
        return {"role": role_name, "group": group_name, "assigned": True}

    def remove_role_from_group(self, role_name, group_name):
        """DELETE /rest/security/roles/role/{role}/group/{name} — remove a role from a group.

        Args:
            role_name: Role name.
            group_name: Group name.

        Example::

            client.remove_role_from_group("ROLE_EDITOR", "editors")
        """
        self._delete(f"security/roles/role/{role_name}/group/{group_name}")
        return {"role": role_name, "group": group_name, "removed": True}

    def list_role_services(self):
        """GET /rest/security/roles/services.json — list available role services.

        Example::

            services = client.list_role_services()
        """
        return self._get("security/roles/services.json").json()

    # ═══════════════════════════════════════════════════════════════════════
    # SECURITY — ACCESS RULES
    # ═══════════════════════════════════════════════════════════════════════

    def get_data_access_rules(self):
        """GET /rest/security/acl/layers.json — get data (layer) access rules.

        Returns a dict mapping rule patterns to role lists.

        Rule format: ``"workspace.layer.accessMode"`` where accessMode is
        ``r`` (read), ``w`` (write), or ``a`` (admin).

        Example::

            rules = client.get_data_access_rules()
            # {"*.*.r": "*", "topp.*.w": "ROLE_EDITOR,ROLE_ADMIN"}
        """
        return self._get("security/acl/layers.json").json()

    def set_data_access_rules(self, rules):
        """POST /rest/security/acl/layers.json — add data access rules.

        Args:
            rules: Dict of ``"workspace.layer.mode": "ROLE,..."`` entries.

        Example::

            client.set_data_access_rules({
                "topp.*.r": "*",
                "topp.*.w": "ROLE_EDITOR,ROLE_ADMIN",
                "topp.secret_layer.r": "ROLE_ADMIN",
            })
        """
        self._post("security/acl/layers.json", json=rules)
        return {"updated": True}

    def update_data_access_rules(self, rules):
        """PUT /rest/security/acl/layers.json — replace all data access rules.

        Args:
            rules: Complete dict of rules (replaces existing).

        Example::

            client.update_data_access_rules({"*.*.r": "*", "*.*.w": "ROLE_ADMIN"})
        """
        self._put("security/acl/layers.json", json=rules)
        return {"updated": True}

    def delete_data_access_rule(self, rule):
        """DELETE /rest/security/acl/layers/{rule} — delete a single data access rule.

        Args:
            rule: Rule pattern, e.g. ``"topp.*.w"``.

        Example::

            client.delete_data_access_rule("topp.*.w")
        """
        self._delete(f"security/acl/layers/{rule}")
        return {"rule": rule, "deleted": True}

    def get_service_access_rules(self):
        """GET /rest/security/acl/services.json — get OGC service access rules.

        Rule format: ``"service.operation"`` → ``"ROLE,..."``.
        E.g. ``"wfs.GetFeature": "ROLE_AUTHENTICATED"``.

        Example::

            rules = client.get_service_access_rules()
        """
        return self._get("security/acl/services.json").json()

    def set_service_access_rules(self, rules):
        """POST /rest/security/acl/services.json — add service access rules.

        Args:
            rules: Dict of ``"service.operation": "ROLE,..."`` entries.

        Example::

            client.set_service_access_rules({
                "wfs.Transaction": "ROLE_EDITOR",
                "wms.*": "*",
            })
        """
        self._post("security/acl/services.json", json=rules)
        return {"updated": True}

    def update_service_access_rules(self, rules):
        """PUT /rest/security/acl/services.json — replace all service access rules.

        Args:
            rules: Complete dict of rules.

        Example::

            client.update_service_access_rules({"wms.*": "*", "wfs.*": "ROLE_AUTHENTICATED"})
        """
        self._put("security/acl/services.json", json=rules)
        return {"updated": True}

    def delete_service_access_rule(self, rule):
        """DELETE /rest/security/acl/services/{rule} — delete a service access rule.

        Args:
            rule: Rule pattern, e.g. ``"wfs.Transaction"``.

        Example::

            client.delete_service_access_rule("wfs.Transaction")
        """
        self._delete(f"security/acl/services/{rule}")
        return {"rule": rule, "deleted": True}

    def get_rest_access_rules(self):
        """GET /rest/security/acl/rest.json — get REST API access rules.

        Rule format: ``"pathPattern;httpMethods"`` → ``"ROLE,..."``.

        Example::

            rules = client.get_rest_access_rules()
        """
        return self._get("security/acl/rest.json").json()

    def set_rest_access_rules(self, rules):
        """POST /rest/security/acl/rest.json — add REST access rules.

        Args:
            rules: Dict of rule entries.

        Example::

            client.set_rest_access_rules({
                "/rest/**;GET": "ROLE_AUTHENTICATED",
                "/rest/**;POST,PUT,DELETE": "ROLE_ADMIN",
            })
        """
        self._post("security/acl/rest.json", json=rules)
        return {"updated": True}

    def update_rest_access_rules(self, rules):
        """PUT /rest/security/acl/rest.json — replace all REST access rules.

        Args:
            rules: Complete dict of rules.

        Example::

            client.update_rest_access_rules({"/rest/**;GET,POST,PUT,DELETE": "ROLE_ADMIN"})
        """
        self._put("security/acl/rest.json", json=rules)
        return {"updated": True}

    def delete_rest_access_rule(self, rule):
        """DELETE /rest/security/acl/rest/{rule} — delete a REST access rule.

        Args:
            rule: Rule pattern.

        Example::

            client.delete_rest_access_rule("/rest/**;GET")
        """
        self._delete(f"security/acl/rest/{rule}")
        return {"rule": rule, "deleted": True}

    # ── Catalog mode ──

    def get_catalog_mode(self):
        """GET /rest/security/acl/catalog.json — get catalog security mode.

        Example::

            mode = client.get_catalog_mode()
            print(mode)  # {"mode": "HIDE"}
        """
        return self._get("security/acl/catalog.json").json()

    def update_catalog_mode(self, mode):
        """PUT /rest/security/acl/catalog.json — set catalog security mode.

        Args:
            mode: ``"HIDE"`` (hide unauthorized layers — default and most secure),
                ``"MIXED"`` (show metadata but deny data access),
                or ``"CHALLENGE"`` (prompt for credentials).

        Example::

            client.update_catalog_mode("HIDE")
        """
        self._put("security/acl/catalog.json", json={"mode": mode})
        return {"mode": mode, "updated": True}

    # ── Master password ──

    def get_master_password(self):
        """GET /rest/security/masterpw.json — get the master password (encrypted).

        Example::

            pw = client.get_master_password()
        """
        return self._get("security/masterpw.json").json()

    def update_master_password(self, old_password, new_password):
        """PUT /rest/security/masterpw.json — change the master password.

        The master password is used to encrypt the keystore and other
        sensitive configuration.

        Args:
            old_password: Current master password.
            new_password: New master password.

        Example::

            client.update_master_password("geoserver", "new_secure_pass")
        """
        self._put("security/masterpw.json", json={"oldMasterPassword": old_password, "newMasterPassword": new_password})
        return {"updated": True}

    # ── Auth filters and providers ──

    def list_auth_filters(self):
        """GET /rest/security/auth/filters.json — list authentication filters.

        Built-in filters include ``basic``, ``form``, ``anonymous``,
        ``rememberme``, ``digest``.

        Example::

            filters = client.list_auth_filters()
        """
        return self._get("security/auth/filters.json").json()

    def get_auth_filter(self, name):
        """GET /rest/security/auth/filters/{name}.json — get auth filter details.

        Args:
            name: Filter name.

        Example::

            f = client.get_auth_filter("basic")
        """
        return self._get(f"security/auth/filters/{name}.json").json()

    def list_auth_providers(self):
        """GET /rest/security/auth/providers.json — list authentication providers.

        Example::

            providers = client.list_auth_providers()
        """
        return self._get("security/auth/providers.json").json()

    def get_auth_provider(self, name):
        """GET /rest/security/auth/providers/{name}.json — get auth provider details.

        Args:
            name: Provider name.

        Example::

            p = client.get_auth_provider("default")
        """
        return self._get(f"security/auth/providers/{name}.json").json()

    def get_auth_filter_chain(self):
        """GET /rest/security/auth/chain.json — get the authentication filter chain.

        Example::

            chain = client.get_auth_filter_chain()
        """
        return self._get("security/auth/chain.json").json()

    def update_auth_filter_chain(self, chain):
        """PUT /rest/security/auth/chain.json — update the authentication filter chain.

        Args:
            chain: Filter chain configuration dict.

        Example::

            client.update_auth_filter_chain(chain_config)
        """
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
        except requests.ConnectionError as exc:
            raise GeoServerError(f"Cannot connect to GeoWebCache at {url}") from exc
        if resp.status_code >= 400:
            raise GeoServerError(
                f"GWC API error: {resp.status_code} {resp.reason}",
                status_code=resp.status_code,
                response_text=resp.text,
            )
        return resp

    # ── GWC Layers ──

    def gwc_list_layers(self):
        """GET /gwc/rest/layers.json — list all GeoWebCache tile layers.

        Example::

            layers = client.gwc_list_layers()
        """
        return self._gwc_request("GET", "layers.json").json()

    def gwc_get_layer(self, name):
        """GET /gwc/rest/layers/{name}.json — get tile layer configuration.

        Args:
            name: Tile layer name (usually ``"workspace:layername"``).

        Example::

            lyr = client.gwc_get_layer("topp:roads")
        """
        return self._gwc_request("GET", f"layers/{name}.json").json()

    def gwc_update_layer(self, name, config):
        """PUT /gwc/rest/layers/{name}.json — update tile layer configuration.

        Args:
            name: Tile layer name.
            config: Complete layer configuration dict.

        Example::

            client.gwc_update_layer("topp:roads", updated_config)
        """
        self._gwc_request("PUT", f"layers/{name}.json", json=config)
        return {"name": name, "updated": True}

    def gwc_delete_layer(self, name):
        """DELETE /gwc/rest/layers/{name}.json — delete a tile layer.

        Args:
            name: Tile layer name.

        Example::

            client.gwc_delete_layer("topp:old_layer")
        """
        self._gwc_request("DELETE", f"layers/{name}.json")
        return {"name": name, "deleted": True}

    # ── GWC Seed / Truncate ──

    def gwc_seed(self, layer_name, seed_request):
        """POST /gwc/rest/seed/{layer}.json — seed, reseed, or truncate tiles.

        Args:
            layer_name: Tile layer name (e.g. ``"topp:roads"``).
            seed_request: Seed request dict. Structure::

                {"seedRequest": {
                    "name": "topp:roads",
                    "type": "seed",          # "seed", "reseed", or "truncate"
                    "zoomStart": 0,
                    "zoomStop": 12,
                    "gridSetId": "EPSG:4326",
                    "format": "image/png",
                    "threadCount": 4,
                }}

        Example::

            client.gwc_seed("topp:roads", {
                "seedRequest": {
                    "name": "topp:roads",
                    "type": "seed",
                    "zoomStart": 0, "zoomStop": 10,
                    "gridSetId": "EPSG:4326",
                    "format": "image/png",
                    "threadCount": 2,
                }
            })
        """
        self._gwc_request("POST", f"seed/{layer_name}.json", json=seed_request)
        return {"layer": layer_name, "seeded": True}

    def gwc_seed_status(self, layer_name=None):
        """GET /gwc/rest/seed[/{layer}].json — get running/pending seed tasks.

        Args:
            layer_name: Optional layer name to filter status.

        Example::

            status = client.gwc_seed_status("topp:roads")
        """
        path = f"seed/{layer_name}.json" if layer_name else "seed.json"
        return self._gwc_request("GET", path).json()

    def gwc_terminate_seed(self, layer_name=None):
        """POST /gwc/rest/seed[/{layer}] — terminate running seed tasks.

        Args:
            layer_name: Optional layer to terminate (all tasks if omitted).

        Example::

            client.gwc_terminate_seed("topp:roads")
            client.gwc_terminate_seed()  # terminate all
        """
        path = f"seed/{layer_name}" if layer_name else "seed"
        self._gwc_request(
            "POST", path, data=b"kill_all=all", headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        return {"terminated": True}

    def gwc_mass_truncate(self, request_type="truncateLayer", layer_name=None):
        """POST /gwc/rest/masstruncate — mass truncate tile cache.

        Args:
            request_type: Truncation type (default ``"truncateLayer"``).
            layer_name: Layer to truncate (required for ``truncateLayer``).

        Example::

            client.gwc_mass_truncate(layer_name="topp:roads")
        """
        payload = {"truncateLayer": {"layerName": layer_name}} if layer_name else {}
        self._gwc_request("POST", "masstruncate", json=payload)
        return {"truncated": True}

    # ── GWC Grid Sets ──

    def gwc_list_gridsets(self):
        """GET /gwc/rest/gridsets.json — list available grid sets.

        Built-in grid sets: ``EPSG:4326``, ``EPSG:900913``, ``GlobalCRS84Pixel``.

        Example::

            gridsets = client.gwc_list_gridsets()
        """
        return self._gwc_request("GET", "gridsets.json").json()

    def gwc_get_gridset(self, name):
        """GET /gwc/rest/gridsets/{name}.json — get grid set configuration.

        Args:
            name: Grid set name.

        Example::

            gs = client.gwc_get_gridset("EPSG:4326")
        """
        return self._gwc_request("GET", f"gridsets/{name}.json").json()

    def gwc_create_gridset(self, name, config):
        """PUT /gwc/rest/gridsets/{name}.json — create a custom grid set.

        Args:
            name: Grid set name.
            config: Grid set configuration dict with ``srs``, ``extent``,
                ``resolutions`` or ``scaleDenominators``, ``tileWidth``,
                ``tileHeight``.

        Example::

            client.gwc_create_gridset("MyGrid", {
                "gridSet": {
                    "name": "MyGrid",
                    "srs": {"number": 4326},
                    "extent": {"coords": {"double": [-180, -90, 180, 90]}},
                    "tileWidth": 256, "tileHeight": 256,
                }
            })
        """
        self._gwc_request("PUT", f"gridsets/{name}.json", json=config)
        return {"name": name, "created": True}

    def gwc_delete_gridset(self, name):
        """DELETE /gwc/rest/gridsets/{name}.json — delete a custom grid set.

        Args:
            name: Grid set name.

        Example::

            client.gwc_delete_gridset("MyGrid")
        """
        self._gwc_request("DELETE", f"gridsets/{name}.json")
        return {"name": name, "deleted": True}

    # ── GWC Blob Stores ──

    def gwc_list_blobstores(self):
        """GET /gwc/rest/blobstores.json — list blob stores.

        Example::

            stores = client.gwc_list_blobstores()
        """
        return self._gwc_request("GET", "blobstores.json").json()

    def gwc_get_blobstore(self, name):
        """GET /gwc/rest/blobstores/{name}.json — get blob store configuration.

        Args:
            name: Blob store name.

        Example::

            bs = client.gwc_get_blobstore("default")
        """
        return self._gwc_request("GET", f"blobstores/{name}.json").json()

    def gwc_create_blobstore(self, name, config):
        """PUT /gwc/rest/blobstores/{name}.json — create a blob store.

        Args:
            name: Blob store name.
            config: Blob store configuration. Types include ``FileBlobStore``
                (local disk) and ``S3BlobStore`` (AWS S3).

        Example::

            client.gwc_create_blobstore("fast_disk", {
                "FileBlobStore": {
                    "id": "fast_disk",
                    "enabled": True,
                    "baseDirectory": "/data/gwc-cache",
                }
            })
        """
        self._gwc_request("PUT", f"blobstores/{name}.json", json=config)
        return {"name": name, "created": True}

    def gwc_delete_blobstore(self, name):
        """DELETE /gwc/rest/blobstores/{name}.json — delete a blob store.

        Args:
            name: Blob store name.

        Example::

            client.gwc_delete_blobstore("old_cache")
        """
        self._gwc_request("DELETE", f"blobstores/{name}.json")
        return {"name": name, "deleted": True}

    # ── GWC Disk Quota ──

    def gwc_get_diskquota(self):
        """GET /gwc/rest/diskquota.json — get disk quota configuration.

        Example::

            quota = client.gwc_get_diskquota()
            print(quota.get("enabled", False))
        """
        return self._gwc_request("GET", "diskquota.json").json()

    def gwc_update_diskquota(self, config):
        """PUT /gwc/rest/diskquota.json — update disk quota configuration.

        Args:
            config: Disk quota config dict with ``enabled``, ``diskBlockSize``,
                ``cacheCleanUpFrequency``, ``cacheCleanUpUnits``,
                ``globalExpirationPolicyName``, ``globalQuota``.

        Example::

            client.gwc_update_diskquota({
                "enabled": True,
                "diskBlockSize": 4096,
                "cacheCleanUpFrequency": 10,
                "cacheCleanUpUnits": "SECONDS",
                "globalExpirationPolicyName": "LFU",
                "globalQuota": {"value": 500, "units": "MiB"},
            })
        """
        self._gwc_request("PUT", "diskquota.json", json=config)
        return {"updated": True}

    # ── GWC Global config ──

    def gwc_get_global(self):
        """GET /gwc/rest/global.json — get GWC global configuration.

        Example::

            config = client.gwc_get_global()
        """
        return self._gwc_request("GET", "global.json").json()

    def gwc_update_global(self, config):
        """PUT /gwc/rest/global.json — update GWC global configuration.

        Args:
            config: Global config dict with ``serviceInformation``,
                ``runtimeStatsEnabled``, ``wmtsCiteCompliant``, etc.

        Example::

            client.gwc_update_global({"runtimeStatsEnabled": True})
        """
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
        """WMS GetCapabilities — service metadata and layer listing.

        Args:
            version: WMS version (``"1.1.1"`` or ``"1.3.0"``).

        Example::

            xml = client.wms_getcapabilities()
        """
        resp = self._ogc_request("wms", {"service": "WMS", "version": version, "request": "GetCapabilities"})
        return resp.text

    def wms_getmap(
        self,
        layers,
        bbox,
        width=800,
        height=600,
        srs="EPSG:4326",
        format="image/png",
        styles="",
        transparent=True,
        **extra,
    ):
        """WMS GetMap — render a map image.

        Args:
            layers: Comma-separated layer names, e.g. ``"topp:roads,topp:rivers"``.
            bbox: Bounding box as ``"minx,miny,maxx,maxy"`` string.
            width: Image width in pixels (default 800).
            height: Image height in pixels (default 600).
            srs: Spatial reference system (default ``"EPSG:4326"``).
            format: Output format — ``"image/png"``, ``"image/jpeg"``,
                ``"image/gif"``, ``"application/pdf"``, ``"image/svg+xml"``.
            styles: Comma-separated style names (empty string for defaults).
            transparent: Transparent background (default True, PNG only).
            **extra: Additional WMS params (e.g. ``CQL_FILTER``, ``ENV``,
                ``TIME``, ``ELEVATION``, ``SLD_BODY``).

        Returns:
            Image bytes.

        Example::

            img = client.wms_getmap("topp:roads", "-180,-90,180,90",
                width=1024, height=768, format="image/png")
            with open("map.png", "wb") as f:
                f.write(img)
        """
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
        return self._ogc_request("wms", params).content

    def wms_getfeatureinfo(
        self,
        layers,
        bbox,
        width,
        height,
        x,
        y,
        query_layers=None,
        info_format="application/json",
        srs="EPSG:4326",
        feature_count=10,
        **extra,
    ):
        """WMS GetFeatureInfo — query feature attributes at a map pixel.

        Args:
            layers: Comma-separated layer names.
            bbox: Bounding box string.
            width: Map image width.
            height: Map image height.
            x: Pixel X coordinate to query.
            y: Pixel Y coordinate to query.
            query_layers: Layers to query (defaults to ``layers``).
            info_format: Response format — ``"application/json"``,
                ``"text/html"``, ``"application/vnd.ogc.gml"``, ``"text/plain"``.
            srs: Spatial reference system.
            feature_count: Max features to return (default 10).
            **extra: Additional WMS params.

        Returns:
            JSON dict (if info_format is JSON) or text string.

        Example::

            info = client.wms_getfeatureinfo("topp:roads",
                "-180,-90,180,90", 800, 600, 400, 300)
            for feat in info["features"]:
                print(feat["properties"])
        """
        params = {
            "service": "WMS",
            "version": "1.1.1",
            "request": "GetFeatureInfo",
            "layers": layers,
            "query_layers": query_layers or layers,
            "bbox": bbox,
            "width": width,
            "height": height,
            "x": x,
            "y": y,
            "srs": srs,
            "info_format": info_format,
            "feature_count": feature_count,
            **extra,
        }
        resp = self._ogc_request("wms", params)
        if "json" in info_format:
            return resp.json()
        return resp.text

    def wms_getlegendgraphic(self, layer, format="image/png", width=20, height=20, style=None, **extra):
        """WMS GetLegendGraphic — render a legend image for a layer.

        Args:
            layer: Layer name.
            format: Image format (default ``"image/png"``).
            width: Legend symbol width (default 20).
            height: Legend symbol height (default 20).
            style: Specific style name (default: layer's default style).
            **extra: Additional params (e.g. ``SCALE``, ``RULE``).

        Returns:
            Image bytes.

        Example::

            legend = client.wms_getlegendgraphic("topp:roads")
            with open("legend.png", "wb") as f:
                f.write(legend)
        """
        params = {
            "service": "WMS",
            "version": "1.1.1",
            "request": "GetLegendGraphic",
            "layer": layer,
            "format": format,
            "width": width,
            "height": height,
            **extra,
        }
        if style:
            params["style"] = style
        return self._ogc_request("wms", params).content

    # ── WFS ──

    def wfs_getcapabilities(self, version="2.0.0"):
        """WFS GetCapabilities — service metadata and feature type listing.

        Args:
            version: WFS version (``"2.0.0"`` or ``"1.1.0"``).

        Example::

            xml = client.wfs_getcapabilities()
        """
        resp = self._ogc_request("wfs", {"service": "WFS", "version": version, "request": "GetCapabilities"})
        return resp.text

    def wfs_describefeaturetype(self, typenames, version="2.0.0", output_format="application/json"):
        """WFS DescribeFeatureType — get the schema of a feature type.

        Args:
            typenames: Feature type name(s), e.g. ``"topp:roads"``.
            version: WFS version.
            output_format: ``"application/json"`` or ``"text/xml; subtype=gml/3.1.1"``.

        Returns:
            JSON dict (if JSON format) or XML text.

        Example::

            schema = client.wfs_describefeaturetype("topp:roads")
            for ft in schema["featureTypes"]:
                for prop in ft["properties"]:
                    print(prop["name"], prop["type"])
        """
        params = {
            "service": "WFS",
            "version": version,
            "request": "DescribeFeatureType",
            "typeNames": typenames,
            "outputFormat": output_format,
        }
        resp = self._ogc_request("wfs", params)
        if "json" in output_format:
            return resp.json()
        return resp.text

    def wfs_getfeature(
        self,
        typenames,
        format="application/json",
        max_features=None,
        cql_filter=None,
        bbox=None,
        srs="EPSG:4326",
        **extra,
    ):
        """WFS GetFeature — retrieve vector features.

        Args:
            typenames: Feature type name(s), e.g. ``"topp:roads"``.
            format: Output format — ``"application/json"`` (GeoJSON),
                ``"GML2"``, ``"GML3"``, ``"csv"``, ``"shape-zip"``.
            max_features: Maximum features to return (None = no limit).
            cql_filter: CQL filter expression, e.g.
                ``"name = 'Main Street'"`` or ``"population > 10000"``.
            bbox: Bounding box filter as ``"minx,miny,maxx,maxy[,srs]"``.
            srs: Output SRS (default ``"EPSG:4326"``).
            **extra: Additional WFS params (e.g. ``propertyName``,
                ``sortBy``, ``startIndex``).

        Returns:
            GeoJSON dict (if JSON format) or text string.

        Example::

            features = client.wfs_getfeature("topp:roads",
                max_features=100, cql_filter="type = 'highway'")
            for f in features["features"]:
                print(f["properties"]["name"])
        """
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
        resp = self._ogc_request("wfs", params)
        if "json" in format.lower():
            return resp.json()
        return resp.text

    # ── WCS ──

    def wcs_getcapabilities(self, version="2.0.1"):
        """WCS GetCapabilities — service metadata and coverage listing.

        Args:
            version: WCS version (``"2.0.1"`` or ``"1.1.1"``).

        Example::

            xml = client.wcs_getcapabilities()
        """
        resp = self._ogc_request("wcs", {"service": "WCS", "version": version, "request": "GetCapabilities"})
        return resp.text

    def wcs_describecoverage(self, coverage_id, version="2.0.1"):
        """WCS DescribeCoverage — get coverage metadata (grid, CRS, bands).

        Args:
            coverage_id: Coverage identifier, e.g. ``"nurc:DEM"``.
            version: WCS version.

        Example::

            xml = client.wcs_describecoverage("nurc:DEM")
        """
        params = {"service": "WCS", "version": version, "request": "DescribeCoverage", "CoverageId": coverage_id}
        return self._ogc_request("wcs", params).text

    def wcs_getcoverage(self, coverage_id, format="image/tiff", bbox=None, srs="EPSG:4326", **extra):
        """WCS GetCoverage — download raster data.

        Args:
            coverage_id: Coverage identifier, e.g. ``"nurc:DEM"``.
            format: Output format — ``"image/tiff"`` (GeoTIFF), ``"image/png"``,
                ``"application/x-netcdf"``.
            bbox: Bounding box as ``"minx,miny,maxx,maxy"`` string. Converted
                to WCS 2.0 subset parameters automatically.
            srs: Spatial reference system.
            **extra: Additional WCS params (e.g. ``subset`` for manual
                subsetting, ``scalefactor``).

        Returns:
            Raster file bytes.

        Example::

            tiff = client.wcs_getcoverage("nurc:DEM",
                bbox="10.0,46.0,13.0,48.0")
            with open("dem.tif", "wb") as f:
                f.write(tiff)
        """
        params = {
            "service": "WCS",
            "version": "2.0.1",
            "request": "GetCoverage",
            "CoverageId": coverage_id,
            "format": format,
            **extra,
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
        """PUT /rest/.../datastores/{store}/file.shp — upload a zipped shapefile.

        Creates/replaces a data store and auto-publishes contained layers.
        The ZIP must contain at minimum ``.shp``, ``.shx``, ``.dbf`` files.

        Args:
            workspace: Target workspace.
            store: Data store name (created if it doesn't exist).
            zip_path: Path to the ZIP file on disk.

        Example::

            client.upload_shapefile("topp", "roads", "/data/roads.zip")
        """
        with open(zip_path, "rb") as f:
            data = f.read()
        self._request(
            "PUT",
            f"workspaces/{workspace}/datastores/{store}/file.shp",
            data=data,
            headers={"Content-Type": "application/zip"},
        )
        return {"workspace": workspace, "store": store, "uploaded": True}

    def upload_geotiff(self, workspace, store, tiff_path):
        """PUT /rest/.../coveragestores/{store}/file.geotiff — upload a GeoTIFF.

        Creates/replaces a coverage store and auto-publishes the raster.

        Args:
            workspace: Target workspace.
            store: Coverage store name (created if it doesn't exist).
            tiff_path: Path to the GeoTIFF file on disk.

        Example::

            client.upload_geotiff("nurc", "elevation", "/data/dem.tif")
        """
        with open(tiff_path, "rb") as f:
            data = f.read()
        self._request(
            "PUT",
            f"workspaces/{workspace}/coveragestores/{store}/file.geotiff",
            data=data,
            headers={"Content-Type": "image/tiff"},
        )
        return {"workspace": workspace, "store": store, "uploaded": True}

    def upload_geopackage(self, workspace, store, gpkg_path):
        """PUT /rest/.../datastores/{store}/file.gpkg — upload a GeoPackage.

        Creates/replaces a data store from a GeoPackage file.

        Args:
            workspace: Target workspace.
            store: Data store name (created if it doesn't exist).
            gpkg_path: Path to the GeoPackage file on disk.

        Example::

            client.upload_geopackage("topp", "my_data", "/data/places.gpkg")
        """
        with open(gpkg_path, "rb") as f:
            data = f.read()
        self._request(
            "PUT",
            f"workspaces/{workspace}/datastores/{store}/file.gpkg",
            data=data,
            headers={"Content-Type": "application/geopackage+sqlite3"},
        )
        return {"workspace": workspace, "store": store, "uploaded": True}

    def upload_style(self, name, sld_path, workspace=None):
        """Upload an SLD style from a file path.

        Convenience wrapper around :meth:`create_style` that reads the file.

        Args:
            name: Style name.
            sld_path: Path to the SLD XML file on disk.
            workspace: Optional workspace scope.

        Example::

            client.upload_style("roads_style", "/data/styles/roads.sld")
        """
        with open(sld_path) as f:
            sld_body = f.read()
        return self.create_style(name, sld_body, workspace=workspace)

    # ═══════════════════════════════════════════════════════════════════════
    # URL CHECK
    # ═══════════════════════════════════════════════════════════════════════

    def url_check(self, url):
        """POST /rest/urlchecks — validate that a URL is reachable from GeoServer.

        Useful for testing remote store URLs before creating cascaded stores.

        Args:
            url: URL to validate.

        Example::

            client.url_check("https://example.com/geoserver/wms?service=WMS&request=GetCapabilities")
        """
        self._post("urlchecks", json={"urlCheck": {"url": url}})
        return {"url": url, "valid": True}
