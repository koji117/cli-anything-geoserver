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
        │   ├── geoserver_backend.py      # REST API client (1078 lines, 120+ methods)
        │   └── repl_skin.py              # Unified REPL skin
        └── tests/
            ├── TEST.md                   # Test plan + results
            ├── test_core.py              # 84 unit tests (mocked, no server needed)
            └── test_full_e2e.py          # ~20 E2E tests (requires GeoServer)
```
