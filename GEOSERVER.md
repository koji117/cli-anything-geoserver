# GeoServer CLI Harness — SOP

## Overview

GeoServer is a Java-based open-source server for sharing, processing, and editing geospatial data via OGC standards (WMS, WFS, WCS, WMTS). This CLI harness wraps GeoServer's REST API and OGC services to provide a stateful, agent-friendly command-line interface.

**Key difference from other cli-anything harnesses:** GeoServer is a _server application_, not a desktop GUI. The "backend" is GeoServer's REST API (`/rest/*`) and OGC service endpoints (`/wms`, `/wfs`, `/wcs`), not a local binary. A running GeoServer instance is the hard dependency.

## Architecture

```
cli-anything-geoserver
    │
    ├── REST API (/geoserver/rest/*)
    │   ├── Workspaces, Namespaces
    │   ├── DataStores, CoverageStores
    │   ├── FeatureTypes, Coverages
    │   ├── Layers, LayerGroups
    │   ├── Styles (SLD/CSS)
    │   ├── Service Settings (WMS/WFS/WCS/WMTS)
    │   ├── Security (users, roles, access rules)
    │   └── System (reload, logging, fonts)
    │
    └── OGC Services (for export)
        ├── WMS GetMap → map images (PNG, JPEG, TIFF, PDF, SVG)
        ├── WFS GetFeature → vector data (GeoJSON, GML, CSV, Shapefile ZIP)
        └── WCS GetCoverage → raster data (GeoTIFF)
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
├── DataStore (vector data connection)
│   └── FeatureType (published vector resource)
│       └── Layer (visible publication)
├── CoverageStore (raster data connection)
│   └── Coverage (published raster resource)
│       └── Layer (visible publication)
├── WMSStore (cascaded WMS)
│   └── WMSLayer
└── Styles (SLD/CSS definitions)
```

| GeoServer Concept | REST Path | CLI Command |
|---|---|---|
| Workspace | `/rest/workspaces` | `workspace` |
| DataStore | `/rest/workspaces/{ws}/datastores` | `store create-datastore` |
| CoverageStore | `/rest/workspaces/{ws}/coveragestores` | `store create-coveragestore` |
| FeatureType | `/rest/workspaces/{ws}/datastores/{ds}/featuretypes` | `layer publish --type feature` |
| Coverage | `/rest/workspaces/{ws}/coveragestores/{cs}/coverages` | `layer publish --type coverage` |
| Layer | `/rest/layers` | `layer` |
| LayerGroup | `/rest/layergroups` | `layergroup` |
| Style | `/rest/styles` | `style` |
| WMS/WFS/WCS Settings | `/rest/services/{svc}/settings` | `service settings` |

## Command Groups

### server
- `server status` — GeoServer version and build info
- `server reload` — Reload the catalog from disk

### workspace
- `workspace list` — List all workspaces
- `workspace create <name>` — Create a workspace
- `workspace get <name>` — Get workspace details
- `workspace delete <name> [--recurse]` — Delete a workspace

### store
- `store list -w <workspace>` — List all stores
- `store create-datastore <name> -w <ws> -p key=value` — Create vector store
- `store create-coveragestore <name> -w <ws> --url <path>` — Create raster store
- `store get <name> -w <ws>` — Get store details
- `store delete <name> -w <ws> [--recurse]` — Delete a store
- `store upload-shapefile <name> -w <ws> --file <zip>` — Upload shapefile
- `store upload-geotiff <name> -w <ws> --file <tif>` — Upload GeoTIFF

### layer
- `layer list` — List all layers
- `layer get <name>` — Get layer details
- `layer publish <name> -w <ws> -s <store>` — Publish a resource as layer
- `layer delete <name>` — Delete a layer

### style
- `style list` — List all styles
- `style get <name> [--body]` — Get style info or SLD body
- `style create <name> --file <sld>` — Create from SLD file
- `style delete <name> [--purge]` — Delete a style

### layergroup
- `layergroup list` — List layer groups
- `layergroup create <name> -l layer1 -l layer2` — Create group
- `layergroup get <name>` — Get group details
- `layergroup delete <name>` — Delete group

### service
- `service settings <wms|wfs|wcs|wmts>` — View service configuration

### export
- `export map <layers> <output> [--bbox] [--width] [--height] [--format]` — WMS GetMap
- `export features <typenames> <output> [--format] [--max-features] [--cql-filter]` — WFS GetFeature
- `export coverage <id> <output> [--format] [--bbox]` — WCS GetCoverage

## Supported Data Sources

| Type | Store Type | Connection Parameters |
|------|-----------|----------------------|
| Shapefile | DataStore | `url=file:data/myshp.shp` |
| PostGIS | DataStore | `host, port, database, user, passwd, dbtype=postgis` |
| GeoTIFF | CoverageStore | `url=file:data/raster.tif` |
| GeoPackage | DataStore | `database=file:data/my.gpkg, dbtype=geopkg` |
| WMS Cascade | WMSStore | `capabilitiesURL=http://...` |

## Output Formats

| Service | Formats |
|---------|---------|
| WMS GetMap | PNG, JPEG, GIF, TIFF, GeoTIFF, PDF, SVG, KML/KMZ |
| WFS GetFeature | GeoJSON, GML 2/3, CSV, Shapefile ZIP, GeoPackage, KML |
| WCS GetCoverage | GeoTIFF, PNG, JPEG, NetCDF |

## Design Decisions

1. **REST API over data directory manipulation** — The CLI uses GeoServer's REST API exclusively, never modifying XML config files directly. This ensures consistency and proper catalog synchronization.

2. **`requests` library as HTTP client** — Standard Python HTTP library, no GeoServer-specific Python bindings needed.

3. **OGC services for export** — Map/feature/coverage export uses the standard OGC service endpoints (WMS/WFS/WCS) rather than REST API, as these are the proper way to retrieve rendered data.

4. **Session state** — Connection parameters and workspace context persist in a JSON session file, enabling stateful REPL workflows.

5. **JSON output mode** — Every command supports `--json` for machine-readable output, making the CLI suitable for agent consumption and scripting pipelines.

6. **Error handling** — Connection failures include clear install/setup instructions. API errors include HTTP status codes and response bodies for debugging.
