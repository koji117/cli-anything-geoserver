# cli-anything-geoserver

CLI harness for [GeoServer](https://geoserver.org/) — an open-source server for sharing geospatial data via OGC standards (WMS, WFS, WCS, WMTS).

## Prerequisites

### GeoServer (Required)

GeoServer must be running and accessible. The easiest way is Docker:

```bash
# Start GeoServer with Docker
docker run -d --name geoserver \
  -p 8080:8080 \
  -e GEOSERVER_ADMIN_USER=admin \
  -e GEOSERVER_ADMIN_PASSWORD=geoserver \
  docker.io/kartoza/geoserver:latest

# Verify it's running
curl -u admin:geoserver http://localhost:8080/geoserver/rest/about/version.json
```

Alternative installations:
- **Binary:** Download from https://geoserver.org/release/stable/ and run `bin/startup.sh`
- **Tomcat:** Deploy the WAR file to Apache Tomcat
- **Homebrew (macOS):** No official formula — use Docker

### Python Dependencies

```bash
pip install -e .
```

## Installation

```bash
cd agent-harness
pip install -e .

# Verify
which cli-anything-geoserver
cli-anything-geoserver --help
```

## Configuration

Set connection via environment variables or CLI options:

```bash
export GEOSERVER_URL=http://localhost:8080/geoserver
export GEOSERVER_USER=admin
export GEOSERVER_PASSWORD=geoserver
```

Or pass as options:
```bash
cli-anything-geoserver --url http://myserver:8080/geoserver --user admin --password secret workspace list
```

## Usage

### Interactive REPL (default)

```bash
cli-anything-geoserver
```

### One-shot Commands

```bash
# Server
cli-anything-geoserver server status
cli-anything-geoserver server reload

# Workspaces
cli-anything-geoserver workspace list
cli-anything-geoserver workspace create my_workspace
cli-anything-geoserver workspace get my_workspace
cli-anything-geoserver workspace delete my_workspace --recurse

# Data Stores
cli-anything-geoserver store list -w my_workspace
cli-anything-geoserver store create-datastore my_pg -w my_workspace \
  -p host=localhost -p port=5432 -p database=mydb -p dbtype=postgis -p user=postgres
cli-anything-geoserver store upload-shapefile my_shp -w my_workspace --file data.zip
cli-anything-geoserver store upload-geotiff my_tiff -w my_workspace --file raster.tif

# Layers
cli-anything-geoserver layer list
cli-anything-geoserver layer get my_layer
cli-anything-geoserver layer publish my_table -w my_workspace -s my_store
cli-anything-geoserver layer delete my_layer

# Styles
cli-anything-geoserver style list
cli-anything-geoserver style get point --body
cli-anything-geoserver style create my_style --file my_style.sld
cli-anything-geoserver style delete my_style --purge

# Layer Groups
cli-anything-geoserver layergroup list
cli-anything-geoserver layergroup create my_group -l layer1 -l layer2

# Service Settings
cli-anything-geoserver service settings wms
cli-anything-geoserver service settings wfs

# Export (via OGC services)
cli-anything-geoserver export map "ws:layer" output.png --bbox "-180,-90,180,90" --width 1024 --height 768
cli-anything-geoserver export features "ws:layer" output.geojson --max-features 100
cli-anything-geoserver export coverage "ws:coverage" output.tif
```

### JSON Output (for agent consumption)

```bash
cli-anything-geoserver --json workspace list
cli-anything-geoserver --json layer list
cli-anything-geoserver --json export map "ws:layer" output.png
```

## Command Reference

| Command Group | Description |
|---------------|-------------|
| `server`      | Server status, version, reload catalog |
| `workspace`   | Create, list, get, delete workspaces |
| `store`       | Manage data stores and coverage stores |
| `layer`       | List, get, publish, delete layers |
| `style`       | Manage SLD/CSS styles |
| `layergroup`  | Manage layer groups |
| `service`     | View/update WMS/WFS/WCS/WMTS settings |
| `export`      | Download maps (WMS), features (WFS), coverages (WCS) |

## Architecture

This CLI wraps GeoServer's REST API (`/rest/*`) for configuration management and OGC services (WMS/WFS/WCS) for data export. It does **not** reimplement any GeoServer functionality — all operations are dispatched to the running GeoServer instance.

```
cli-anything-geoserver
    ├── REST API ──→ /geoserver/rest/*  (config management)
    └── OGC Services ──→ /geoserver/wms, /wfs, /wcs  (data export)
```
