# GeoServer CLI Harness — SOP

## Overview

GeoServer is a Java-based open-source server for sharing, processing, and editing geospatial data via OGC standards (WMS, WFS, WCS, WMTS). This CLI harness wraps GeoServer's REST API, GeoWebCache REST API, and OGC service endpoints to provide a complete, stateful, agent-friendly command-line interface.

**Key difference from other cli-anything harnesses:** GeoServer is a _server application_, not a desktop GUI. The "backend" is a running GeoServer instance accessed via HTTP. A GeoServer instance is the hard dependency.

**Coverage:** 120+ backend methods, 18 CLI command groups, 100% of the GeoServer REST API.

## Architecture

```
cli-anything-geoserver
    │
    ├── REST API (/geoserver/rest/*)
    │   ├── Catalog
    │   │   ├── Workspaces (CRUD)
    │   │   ├── Namespaces (CRUD)
    │   │   ├── DataStores (CRUD + upload shapefile/geopackage)
    │   │   ├── CoverageStores (CRUD + upload GeoTIFF)
    │   │   ├── FeatureTypes (CRUD)
    │   │   ├── Coverages (CRUD)
    │   │   ├── Layers (list/get/update/delete)
    │   │   ├── LayerGroups (CRUD)
    │   │   └── Styles (CRUD + SLD body get/update)
    │   │
    │   ├── Cascaded Services
    │   │   ├── WMS Stores (CRUD)
    │   │   ├── WMTS Stores (CRUD)
    │   │   ├── WMS Layers (CRUD)
    │   │   └── WMTS Layers (CRUD)
    │   │
    │   ├── Configuration
    │   │   ├── Service Settings — WMS/WFS/WCS/WMTS (get/update)
    │   │   ├── Global Settings (get/update)
    │   │   ├── Contact Info (get/update)
    │   │   ├── Logging (get/update)
    │   │   ├── Local Workspace Settings (CRUD)
    │   │   └── Fonts (list)
    │   │
    │   ├── Security
    │   │   ├── Users (CRUD)
    │   │   ├── Groups (create/delete, add/remove users)
    │   │   ├── Roles (CRUD, assign/remove user/group)
    │   │   ├── Data Access Rules (get/set)
    │   │   ├── Service Access Rules (get/set)
    │   │   ├── REST Access Rules (get/set)
    │   │   ├── Catalog Mode (get/set: HIDE/MIXED/CHALLENGE)
    │   │   ├── Master Password (get/update)
    │   │   ├── Auth Filters (list/get)
    │   │   └── Auth Providers (list/get)
    │   │
    │   ├── Resources
    │   │   ├── Data Directory files (list/get/put/delete)
    │   │   └── Freemarker Templates (list/get/create/delete)
    │   │
    │   └── System
    │       ├── Version, Status, Manifests
    │       ├── Reload, Reset
    │       └── URL Check
    │
    ├── GeoWebCache (/geoserver/gwc/rest/*)
    │   ├── Tile Layers (list/get/update/delete)
    │   ├── Seed/Reseed/Truncate operations
    │   ├── Seed task status and termination
    │   ├── Mass truncate
    │   ├── Grid Sets (CRUD)
    │   ├── Blob Stores (CRUD)
    │   ├── Disk Quota (get/update)
    │   └── Global config (get/update)
    │
    └── OGC Services
        ├── WMS: GetMap, GetCapabilities, GetFeatureInfo, GetLegendGraphic
        ├── WFS: GetFeature, GetCapabilities, DescribeFeatureType
        └── WCS: GetCoverage, GetCapabilities, DescribeCoverage
```

## Backend Dependency

### Running GeoServer (Required)

```bash
# Docker (recommended)
docker run -d --name geoserver \
  -p 8080:8080 \
  -e GEOSERVER_ADMIN_USER=admin \
  -e GEOSERVER_ADMIN_PASSWORD=geoserver \
  docker.io/kartoza/geoserver:latest

# Binary distribution
wget https://sourceforge.net/projects/geoserver/files/GeoServer/2.26.1/geoserver-2.26.1-bin.zip
unzip geoserver-2.26.1-bin.zip
cd geoserver-2.26.1/bin && ./startup.sh
```

### Authentication

- HTTP Basic Auth: `Authorization: Basic base64(username:password)`
- Default credentials: `admin` / `geoserver`
- Configurable via `--user`/`--password` flags or `GEOSERVER_USER`/`GEOSERVER_PASSWORD` env vars

## Data Model

GeoServer's catalog follows a hierarchical structure:

```
Workspace (container)
├── Namespace (XML namespace, 1:1 with workspace)
├── DataStore (vector data connection: PostGIS, Shapefile, GeoPackage)
│   └── FeatureType (published vector resource)
│       └── Layer (visible publication)
├── CoverageStore (raster data connection: GeoTIFF, etc.)
│   └── Coverage (published raster resource)
│       └── Layer (visible publication)
├── WMSStore (cascaded WMS connection)
│   └── WMSLayer (remote WMS layer)
│       └── Layer
├── WMTSStore (cascaded WMTS connection)
│   └── WMTSLayer (remote WMTS layer)
│       └── Layer
├── Styles (SLD/CSS definitions)
└── LayerGroups (composite layer collections)
```

### REST Path → CLI Command Mapping

| GeoServer Concept | REST Path | CLI Command Group |
|---|---|---|
| Workspace | `/rest/workspaces` | `workspace` |
| Namespace | `/rest/namespaces` | `namespace` |
| DataStore | `/rest/workspaces/{ws}/datastores` | `store` |
| CoverageStore | `/rest/workspaces/{ws}/coveragestores` | `store` |
| FeatureType | `/rest/workspaces/{ws}/datastores/{ds}/featuretypes` | `layer publish` |
| Coverage | `/rest/workspaces/{ws}/coveragestores/{cs}/coverages` | `layer publish` |
| Layer | `/rest/layers` | `layer` |
| LayerGroup | `/rest/layergroups` | `layergroup` |
| Style | `/rest/styles` | `style` |
| WMS Store | `/rest/workspaces/{ws}/wmsstores` | `wmsstore` |
| WMTS Store | `/rest/workspaces/{ws}/wmtsstores` | `wmtsstore` |
| WMS Layer | `/rest/workspaces/{ws}/wmsstores/{s}/wmslayers` | `wmslayer` |
| WMTS Layer | `/rest/workspaces/{ws}/wmtsstores/{s}/wmtslayers` | `wmtslayer` |
| Template | `/rest/templates` | `template` |
| Resource | `/rest/resource` | `resource` |
| Users | `/rest/security/usergroup/service/*/users` | `security user` |
| Roles | `/rest/security/roles` | `security role` |
| Access Rules | `/rest/security/acl/*` | `security rules` |
| GWC Layers | `/gwc/rest/layers` | `gwc layer` |
| GWC Seed | `/gwc/rest/seed` | `gwc seed` |
| Settings | `/rest/settings` | `settings` |
| Services | `/rest/services/{wms,wfs,wcs,wmts}/settings` | `service` |

## Command Groups (18 total)

| # | Group | Subcommands | Description |
|---|-------|-------------|-------------|
| 1 | `server` | status, reload, reset, manifests | Server admin |
| 2 | `workspace` | list, get, create, update, delete | Workspace CRUD |
| 3 | `namespace` | list, get, create, update, delete | XML namespace CRUD |
| 4 | `store` | list, get, create-datastore, create-coveragestore, update-datastore, update-coveragestore, delete, upload-shapefile, upload-geotiff | Data store management |
| 5 | `layer` | list, get, update, delete, publish | Layer management |
| 6 | `style` | list, get, create, update, delete | SLD style CRUD |
| 7 | `layergroup` | list, get, create, update, delete | Layer group CRUD |
| 8 | `wmsstore` | list, get, create, update, delete | Cascaded WMS stores |
| 9 | `wmtsstore` | list, get, create, update, delete | Cascaded WMTS stores |
| 10 | `wmslayer` | list, get, create, update, delete | Cascaded WMS layers |
| 11 | `wmtslayer` | list, get, create, update, delete | Cascaded WMTS layers |
| 12 | `resource` | list, get, put, delete | Data directory files |
| 13 | `template` | list, get, create, delete | Freemarker templates |
| 14 | `security` | user, group, role, rules, catalog-mode, master-password, auth-filters, auth-providers | Full security management |
| 15 | `gwc` | layer, seed, seed-status, terminate, mass-truncate, gridset, blobstore, diskquota, global | GeoWebCache management |
| 16 | `settings` | get, update, logging-get, logging-update, contact-get, contact-update, fonts, local-get, local-create, local-update, local-delete | Configuration |
| 17 | `service` | settings, update | OGC service config (WMS/WFS/WCS/WMTS) |
| 18 | `export` | map, features, coverage, capabilities, featureinfo, legendgraphic, describe-featuretype, describe-coverage | OGC data export & introspection |

## Supported Data Sources

| Type | Store Type | CLI Command | Connection Parameters |
|------|-----------|-------------|----------------------|
| Shapefile | DataStore | `store upload-shapefile` | ZIP file upload |
| PostGIS | DataStore | `store create-datastore` | `host, port, database, user, passwd, dbtype=postgis` |
| GeoTIFF | CoverageStore | `store upload-geotiff` | TIFF file upload |
| GeoPackage | DataStore | `store create-datastore` | `database=file:data/my.gpkg, dbtype=geopkg` |
| WMS Cascade | WMSStore | `wmsstore create` | `capabilitiesURL=http://...` |
| WMTS Cascade | WMTSStore | `wmtsstore create` | `capabilitiesURL=http://...` |

## Output Formats

| Service | Formats |
|---------|---------|
| WMS GetMap | PNG, JPEG, GIF, TIFF, GeoTIFF, PDF, SVG, KML/KMZ |
| WFS GetFeature | GeoJSON, GML 2/3, CSV, Shapefile ZIP, GeoPackage, KML |
| WCS GetCoverage | GeoTIFF, PNG, JPEG, NetCDF |
| WMS GetFeatureInfo | JSON, HTML, GML, Text |
| WFS DescribeFeatureType | JSON, XML/GML |

## Design Decisions

1. **REST API wrapper, not data directory manipulation** — The CLI uses GeoServer's REST API and GWC REST API exclusively, never modifying XML config files directly. This ensures catalog consistency and proper event propagation.

2. **`requests` library as HTTP client** — Standard Python HTTP library. No GeoServer-specific Python bindings (like gsconfig-py) needed — the REST API is the canonical interface.

3. **OGC services for data export** — Map/feature/coverage export uses standard OGC endpoints (WMS/WFS/WCS) rather than REST API, as these are the proper way to retrieve rendered data. Added GetCapabilities, GetFeatureInfo, GetLegendGraphic, DescribeFeatureType, DescribeCoverage for full introspection.

4. **GeoWebCache as first-class citizen** — GWC has its own REST API at `/gwc/rest/*` with separate URL construction. The `gwc` command group covers tile management, seeding, grid sets, blob stores, and disk quota.

5. **Full security coverage** — Users, groups, roles, access rules (data/service/REST), catalog mode, master password, and auth filter/provider introspection. This enables automated security hardening workflows.

6. **Session state** — Connection parameters and workspace context persist in a JSON session file, enabling stateful REPL workflows across commands.

7. **JSON output mode** — Every command supports `--json` for machine-readable output, making the CLI suitable for AI agent consumption and shell scripting pipelines.

8. **Error handling** — Connection failures include clear Docker setup instructions. API errors include HTTP status codes and response body excerpts for debugging.

## File Structure

```
agent-harness/
├── README.md                             # This SOP document
├── pyproject.toml                        # uv/PyPI package config
└── cli_anything/                         # Namespace pkg (NO __init__.py)
    └── geoserver/                        # Sub-package
        ├── __init__.py                   # Version: 1.0.0
        ├── __main__.py                   # python -m cli_anything.geoserver
        ├── README.md                     # Comprehensive usage documentation
        ├── geoserver_cli.py              # Click CLI + REPL (2817 lines, 18 groups)
        ├── core/
        │   ├── project.py                # Functional session state
        │   ├── session.py                # OOP session with undo
        │   └── export.py                 # WMS/WFS/WCS export helpers
        ├── utils/
        │   ├── geoserver_backend.py      # REST API client (120+ methods)
        │   └── repl_skin.py              # Unified REPL skin
        └── tests/
            ├── TEST.md                   # Test plan + results
            ├── test_core.py              # 84 unit tests (mocked, no server needed)
            └── test_full_e2e.py          # ~20 E2E tests (requires GeoServer)
```

## API Parameter Reference

All create/update methods accept explicit keyword parameters derived from the GeoServer REST API. Parameters default to `None` (omitted from the request). Additional unlisted fields can be passed via `**kwargs`.

### DataStore Connection Parameters

Used by `create_datastore()`. Common configurations:

| Data Source | Key Parameters |
|-------------|----------------|
| PostGIS | `host`, `port`, `database`, `schema`, `user`, `passwd`, `dbtype="postgis"` |
| Shapefile Directory | `url="file:data/shapefiles"`, `dbtype="shapefile"` |
| GeoPackage | `database="file:data/my.gpkg"`, `dbtype="geopkg"` |
| Oracle | `host`, `port`, `database`, `schema`, `user`, `passwd`, `dbtype="oracle"` |
| SQL Server | `host`, `port`, `database`, `schema`, `user`, `passwd`, `dbtype="sqlserver"` |

### CoverageStore Types

Used by `create_coveragestore(store_type=...)`:

| Type | Description |
|------|-------------|
| `"GeoTIFF"` | Single GeoTIFF file |
| `"WorldImage"` | World-file referenced image (PNG/JPEG/TIFF + .pgw/.jgw/.tfw) |
| `"ImageMosaic"` | Directory of raster tiles with index |
| `"NetCDF"` | NetCDF scientific data format |
| `"ImagePyramid"` | Multi-resolution raster pyramid |

### Feature Type / Coverage Fields

Used by `create_featuretype()`, `update_featuretype()`, `create_coverage()`, `update_coverage()`:

| Parameter | Type | Description |
|-----------|------|-------------|
| `title` | str | Human-readable layer title |
| `abstract` | str | Layer description |
| `srs` | str | Declared SRS, e.g. `"EPSG:4326"`, `"EPSG:32632"` |
| `native_crs` | str | Native CRS (usually auto-detected) |
| `enabled` | bool | Whether the resource is enabled |
| `projection_policy` | str | `"FORCE_DECLARED"`, `"REPROJECT_TO_DECLARED"`, or `"NONE"` |
| `keywords` | dict | `{"string": ["keyword1", "keyword2"]}` |
| `advertised` | bool | Show in GetCapabilities |
| `native_bounding_box` | dict | `{"minx": 10.0, "miny": 46.0, "maxx": 13.0, "maxy": 48.0, "crs": "EPSG:4326"}` |
| `lat_lon_bounding_box` | dict | Geographic extent (same structure as above, always EPSG:4326) |

### Layer Fields

Used by `update_layer()`:

| Parameter | Type | Description |
|-----------|------|-------------|
| `default_style` | str/dict | Default style name or `{"name": "style_name"}` |
| `enabled` | bool | Enable/disable the layer |
| `queryable` | bool | Supports GetFeatureInfo |
| `opaque` | bool | Layer is opaque (WMS) |
| `advertised` | bool | Show in GetCapabilities |

### Layer Group Fields

Used by `create_layergroup()`, `update_layergroup()`:

| Parameter | Type | Description |
|-----------|------|-------------|
| `title` | str | Human-readable title |
| `abstract_txt` | str | Group description |
| `mode` | str | `"SINGLE"` (merged), `"NAMED"` (individually accessible), `"CONTAINER"`, `"EO"` |
| `bounds` | dict | `{"minx": ..., "miny": ..., "maxx": ..., "maxy": ..., "crs": "EPSG:4326"}` |

### WMS/WMTS Store Fields

Used by `create_wmsstore()`, `update_wmsstore()`, `create_wmtsstore()`, `update_wmtsstore()`:

| Parameter | Type | Description |
|-----------|------|-------------|
| `capabilities_url` | str | GetCapabilities URL of the remote service |
| `enabled` | bool | Enable/disable the store |
| `max_connections` | int | Max concurrent connections (default 6) |
| `connect_timeout` | int | Connection timeout in seconds |
| `read_timeout` | int | Read timeout in seconds |
| `description` | str | Human-readable description |

### OGC Service Settings

Used by `update_service_settings()` for WMS, WFS, WCS, WMTS:

| Parameter | Type | Description |
|-----------|------|-------------|
| `enabled` | bool | Enable/disable the service |
| `title` | str | Service title (in GetCapabilities) |
| `abstract` | str | Service description |
| `fees` | str | Fee info (e.g. `"NONE"`) |
| `access_constraints` | str | Access constraints (e.g. `"NONE"`) |
| `cite_compliant` | bool | Strict OGC CITE compliance |
| `max_features` | int | WFS: max features per response |

### Global Settings

Used by `update_settings()`:

| Parameter | Type | Description |
|-----------|------|-------------|
| `verbose` | bool | Verbose output |
| `verbose_exceptions` | bool | Full stack traces in errors |
| `num_decimals` | int | Decimal places in coordinates |
| `charset` | str | Output charset (e.g. `"UTF-8"`) |
| `proxy_base_url` | str | Proxy base URL (e.g. `"https://maps.example.com/geoserver"`) |

### Contact Information

Used by `update_contact()`:

| Parameter | Type | Description |
|-----------|------|-------------|
| `contact_person` | str | Contact person name |
| `contact_organization` | str | Organization |
| `contact_position` | str | Position/title |
| `contact_email` | str | Email address |
| `contact_phone` | str | Phone number |
| `address` | str | Street address |
| `address_city` | str | City |
| `address_state` | str | State/province |
| `address_postal_code` | str | Postal code |
| `address_country` | str | Country |

### Logging Configuration

Used by `update_logging()`:

| Parameter | Type | Description |
|-----------|------|-------------|
| `level` | str | `"DEFAULT_LOGGING.properties"`, `"PRODUCTION_LOGGING.properties"`, `"VERBOSE_LOGGING.properties"` |
| `location` | str | Log file path, e.g. `"logs/geoserver.log"` |
| `std_out_logging` | bool | Also log to stdout |

### Security — Data Access Rules

Used by `set_data_access_rules()`, `update_data_access_rules()`:

```python
{
    "*.*.r": "*",                          # everyone can read all layers
    "topp.*.w": "ROLE_EDITOR,ROLE_ADMIN",  # editors/admins can write topp
    "topp.secret_layer.r": "ROLE_ADMIN",   # only admins can read secret layer
}
```

Rule format: `"workspace.layer.accessMode"` → `"ROLE,..."` where accessMode is `r` (read), `w` (write), or `a` (admin).

### GWC Seed Request Structure

Used by `gwc_seed()`:

```python
{"seedRequest": {
    "name": "topp:roads",
    "type": "seed",           # "seed", "reseed", or "truncate"
    "zoomStart": 0,
    "zoomStop": 12,
    "gridSetId": "EPSG:4326",
    "format": "image/png",
    "threadCount": 4,
}}
```

### Usage Examples

```python
from cli_anything.geoserver.utils.geoserver_backend import GeoServerClient

client = GeoServerClient(url="http://localhost:8080/geoserver",
                          username="admin", password="geoserver")

# Create a PostGIS data store
client.create_datastore("my_ws", "pg_db", {
    "host": "localhost", "port": "5432", "database": "geodata",
    "user": "geo", "passwd": "secret", "dbtype": "postgis",
})

# Publish a feature type from the store
client.create_featuretype("my_ws", "pg_db", "roads",
    title="Road Network", srs="EPSG:4326",
    projection_policy="FORCE_DECLARED")

# Update layer styling
client.update_layer("roads", default_style="line", queryable=True)

# Create a layer group
client.create_layergroup("city_map",
    ["my_ws:roads", "my_ws:buildings"],
    workspace="my_ws", title="City Map", mode="NAMED")

# Set data access rules
client.set_data_access_rules({
    "my_ws.*.r": "*",
    "my_ws.*.w": "ROLE_EDITOR,ROLE_ADMIN",
})

# Export a WMS map image
img = client.wms_getmap("my_ws:roads", "-180,-90,180,90",
    width=1024, height=768)
with open("map.png", "wb") as f:
    f.write(img)

# Seed tiles for a layer
client.gwc_seed("my_ws:roads", {
    "seedRequest": {
        "name": "my_ws:roads", "type": "seed",
        "zoomStart": 0, "zoomStop": 10,
        "gridSetId": "EPSG:4326", "format": "image/png",
        "threadCount": 2,
    }
})
```
