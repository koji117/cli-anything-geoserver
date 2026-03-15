# cli-anything-geoserver

Complete CLI harness for [GeoServer](https://geoserver.org/) — an open-source server for sharing geospatial data via OGC standards (WMS, WFS, WCS, WMTS).

**120+ backend methods | 18 command groups | 100% REST API coverage**

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

### Python Dependencies

```bash
uv sync
```

Requires: Python 3.10+, click, prompt-toolkit, requests

## Installation

```bash
cd agent-harness
uv sync

# Verify
uv run cli-anything-geoserver --help

# Or install globally
uv pip install -e .
which cli-anything-geoserver
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

## Quick Start

```bash
# Enter interactive REPL (default when no subcommand)
cli-anything-geoserver

# Or use one-shot commands
cli-anything-geoserver workspace list
cli-anything-geoserver --json layer list
```

---

## Complete Command Reference

### `server` — Server Administration

```bash
cli-anything-geoserver server status              # GeoServer version and build info
cli-anything-geoserver server reload               # Reload catalog from disk
cli-anything-geoserver server reset                # Reset resource and memory caches
cli-anything-geoserver server manifests            # Show installed modules/extensions
```

### `workspace` — Workspace Management

```bash
cli-anything-geoserver workspace list
cli-anything-geoserver workspace create my_workspace
cli-anything-geoserver workspace create my_workspace --isolated
cli-anything-geoserver workspace get my_workspace
cli-anything-geoserver workspace update my_workspace --param name=new_name
cli-anything-geoserver workspace delete my_workspace --recurse
```

### `namespace` — XML Namespace Management

```bash
cli-anything-geoserver namespace list
cli-anything-geoserver namespace create topp http://topp.example.com
cli-anything-geoserver namespace get topp
cli-anything-geoserver namespace update topp --uri http://new.example.com
cli-anything-geoserver namespace delete topp
```

### `store` — Data Store & Coverage Store Management

```bash
# List all stores in a workspace (data + coverage)
cli-anything-geoserver store list -w my_workspace
cli-anything-geoserver store list -w my_workspace --type data
cli-anything-geoserver store list -w my_workspace --type coverage

# Create data stores
cli-anything-geoserver store create-datastore my_pg -w my_workspace \
  -p host=localhost -p port=5432 -p database=mydb -p dbtype=postgis -p user=postgres -p passwd=secret
cli-anything-geoserver store create-datastore my_shp -w my_workspace \
  -p url=file:data/shapefile_dir

# Create coverage stores
cli-anything-geoserver store create-coveragestore my_dem -w my_workspace \
  --url file:data/dem.tif --type GeoTIFF

# Update stores
cli-anything-geoserver store update-datastore my_pg -w my_workspace --param enabled=true
cli-anything-geoserver store update-coveragestore my_dem -w my_workspace --param enabled=false

# Get store details
cli-anything-geoserver store get my_pg -w my_workspace --type data
cli-anything-geoserver store get my_dem -w my_workspace --type coverage

# Upload files directly
cli-anything-geoserver store upload-shapefile my_shp -w my_workspace --file data.zip
cli-anything-geoserver store upload-geotiff my_dem -w my_workspace --file raster.tif

# Delete stores
cli-anything-geoserver store delete my_pg -w my_workspace --type data --recurse
cli-anything-geoserver store delete my_dem -w my_workspace --type coverage --recurse
```

### `layer` — Layer Management

```bash
cli-anything-geoserver layer list
cli-anything-geoserver layer list -w my_workspace
cli-anything-geoserver layer get my_layer
cli-anything-geoserver layer get my_layer -w my_workspace

# Publish a resource as a layer
cli-anything-geoserver layer publish my_table -w my_workspace -s my_store --type feature
cli-anything-geoserver layer publish my_raster -w my_workspace -s my_coveragestore --type coverage

# Update layer settings
cli-anything-geoserver layer update my_layer --param enabled=false --param defaultStyle.name=polygon

# Delete
cli-anything-geoserver layer delete my_layer --recurse
```

### `style` — SLD/CSS Style Management

```bash
cli-anything-geoserver style list
cli-anything-geoserver style list -w my_workspace
cli-anything-geoserver style get point                   # Style metadata
cli-anything-geoserver style get point --body             # Full SLD XML body
cli-anything-geoserver style create my_style --file my_style.sld
cli-anything-geoserver style create my_style --file my_style.sld -w my_workspace
cli-anything-geoserver style update my_style --file updated.sld
cli-anything-geoserver style delete my_style --purge      # Also delete the SLD file
```

### `layergroup` — Layer Group Management

```bash
cli-anything-geoserver layergroup list
cli-anything-geoserver layergroup list -w my_workspace
cli-anything-geoserver layergroup get spearfish
cli-anything-geoserver layergroup create my_group -l topp:states -l topp:roads
cli-anything-geoserver layergroup create my_group -l layer1 -l layer2 -w my_workspace
cli-anything-geoserver layergroup update my_group --param title="Updated Group"
cli-anything-geoserver layergroup delete my_group
```

### `wmsstore` — Cascaded WMS Store Management

```bash
cli-anything-geoserver wmsstore list -w my_workspace
cli-anything-geoserver wmsstore get remote_wms -w my_workspace
cli-anything-geoserver wmsstore create remote_wms -w my_workspace \
  --capabilities-url "http://external-server/wms?service=WMS&version=1.1.1&request=GetCapabilities"
cli-anything-geoserver wmsstore update remote_wms -w my_workspace --param enabled=false
cli-anything-geoserver wmsstore delete remote_wms -w my_workspace --recurse
```

### `wmtsstore` — Cascaded WMTS Store Management

```bash
cli-anything-geoserver wmtsstore list -w my_workspace
cli-anything-geoserver wmtsstore get remote_wmts -w my_workspace
cli-anything-geoserver wmtsstore create remote_wmts -w my_workspace \
  --capabilities-url "http://external-server/wmts?service=WMTS&version=1.0.0&request=GetCapabilities"
cli-anything-geoserver wmtsstore update remote_wmts -w my_workspace --param enabled=false
cli-anything-geoserver wmtsstore delete remote_wmts -w my_workspace --recurse
```

### `wmslayer` — Cascaded WMS Layer Management

```bash
cli-anything-geoserver wmslayer list -w my_workspace -s remote_wms
cli-anything-geoserver wmslayer get remote_roads -w my_workspace -s remote_wms
cli-anything-geoserver wmslayer create remote_roads -w my_workspace -s remote_wms
cli-anything-geoserver wmslayer update remote_roads -w my_workspace -s remote_wms --param enabled=false
cli-anything-geoserver wmslayer delete remote_roads -w my_workspace -s remote_wms
```

### `wmtslayer` — Cascaded WMTS Layer Management

```bash
cli-anything-geoserver wmtslayer list -w my_workspace -s remote_wmts
cli-anything-geoserver wmtslayer get tiles -w my_workspace -s remote_wmts
cli-anything-geoserver wmtslayer create tiles -w my_workspace -s remote_wmts
cli-anything-geoserver wmtslayer update tiles -w my_workspace -s remote_wmts --param enabled=false
cli-anything-geoserver wmtslayer delete tiles -w my_workspace -s remote_wmts
```

### `resource` — Data Directory File Management

```bash
cli-anything-geoserver resource list                        # Root directory
cli-anything-geoserver resource list --path styles           # List styles directory
cli-anything-geoserver resource get styles/point.sld -o point.sld   # Download a file
cli-anything-geoserver resource put styles/custom.sld --file custom.sld --content-type application/xml
cli-anything-geoserver resource delete styles/old.sld
```

### `template` — Freemarker Template Management

```bash
cli-anything-geoserver template list
cli-anything-geoserver template list -w my_workspace
cli-anything-geoserver template list -w my_workspace -s my_store
cli-anything-geoserver template get header.ftl
cli-anything-geoserver template create header.ftl --file header.ftl
cli-anything-geoserver template create header.ftl --file header.ftl -w my_workspace
cli-anything-geoserver template delete header.ftl
```

### `security` — Full Security Management

#### Users

```bash
cli-anything-geoserver security user list
cli-anything-geoserver security user list --service default
cli-anything-geoserver security user get admin
cli-anything-geoserver security user create editor --password secret123
cli-anything-geoserver security user create editor --password secret123 --disabled
cli-anything-geoserver security user update editor --param password=newpass
cli-anything-geoserver security user delete editor
```

#### Groups

```bash
cli-anything-geoserver security group list
cli-anything-geoserver security group create editors
cli-anything-geoserver security group delete editors
cli-anything-geoserver security group add-user editor editors
cli-anything-geoserver security group remove-user editor editors
```

#### Roles

```bash
cli-anything-geoserver security role list
cli-anything-geoserver security role list-user admin          # Roles for a user
cli-anything-geoserver security role list-group editors       # Roles for a group
cli-anything-geoserver security role create ROLE_EDITOR
cli-anything-geoserver security role delete ROLE_EDITOR
cli-anything-geoserver security role assign-user ROLE_EDITOR admin
cli-anything-geoserver security role remove-user ROLE_EDITOR admin
cli-anything-geoserver security role assign-group ROLE_EDITOR editors
cli-anything-geoserver security role remove-group ROLE_EDITOR editors
```

#### Access Rules

```bash
# Data access rules (layer-level)
cli-anything-geoserver security rules data-get
cli-anything-geoserver security rules data-set --rule "topp.*.r=*" --rule "topp.*.w=ROLE_EDITOR"

# Service access rules
cli-anything-geoserver security rules service-get
cli-anything-geoserver security rules service-set --rule "wfs.GetFeature=*" --rule "wfs.Transaction=ROLE_EDITOR"

# REST access rules
cli-anything-geoserver security rules rest-get
cli-anything-geoserver security rules rest-set --rule "/rest/**=ROLE_ADMIN"
```

#### Catalog Mode & Master Password

```bash
cli-anything-geoserver security catalog-mode get
cli-anything-geoserver security catalog-mode set HIDE         # HIDE, MIXED, or CHALLENGE

cli-anything-geoserver security master-password get
cli-anything-geoserver security master-password update --old oldpass --new newpass
```

#### Authentication Filters & Providers

```bash
cli-anything-geoserver security auth-filters list
cli-anything-geoserver security auth-filters get basic
cli-anything-geoserver security auth-providers list
cli-anything-geoserver security auth-providers get default
```

### `gwc` — GeoWebCache Tile Management

#### Tile Layers

```bash
cli-anything-geoserver gwc layer list
cli-anything-geoserver gwc layer get topp:states
cli-anything-geoserver gwc layer update topp:states --config '{"GeoServerLayer": {...}}'
cli-anything-geoserver gwc layer delete topp:states
```

#### Seeding & Truncating

```bash
# Seed tiles for a layer
cli-anything-geoserver gwc seed topp:states \
  --type seed --gridset EPSG:4326 --zoom-start 0 --zoom-stop 10 --format image/png

# Check seed task status
cli-anything-geoserver gwc seed-status
cli-anything-geoserver gwc seed-status --layer topp:states

# Terminate running seed tasks
cli-anything-geoserver gwc terminate
cli-anything-geoserver gwc terminate --layer topp:states

# Mass truncate
cli-anything-geoserver gwc mass-truncate --layer topp:states
```

#### Grid Sets

```bash
cli-anything-geoserver gwc gridset list
cli-anything-geoserver gwc gridset get EPSG:4326
cli-anything-geoserver gwc gridset create my_grid --config '{"gridSet": {...}}'
cli-anything-geoserver gwc gridset delete my_grid
```

#### Blob Stores

```bash
cli-anything-geoserver gwc blobstore list
cli-anything-geoserver gwc blobstore get default
cli-anything-geoserver gwc blobstore create my_store --config '{"FileBlobStore": {...}}'
cli-anything-geoserver gwc blobstore delete my_store
```

#### Disk Quota & Global Config

```bash
cli-anything-geoserver gwc diskquota get
cli-anything-geoserver gwc diskquota update --config '{"enabled": true, "diskBlockSize": 4096}'
cli-anything-geoserver gwc global get
cli-anything-geoserver gwc global update --config '{"serviceInformation": {...}}'
```

### `settings` — Global & Workspace Settings

```bash
# Global settings
cli-anything-geoserver settings get
cli-anything-geoserver settings update --param verbose=true --param numDecimals=8

# Logging
cli-anything-geoserver settings logging-get
cli-anything-geoserver settings logging-update --param level=PRODUCTION_LOGGING.properties

# Contact information
cli-anything-geoserver settings contact-get
cli-anything-geoserver settings contact-update --param contactPerson="Admin" --param contactEmail="admin@example.com"

# Fonts
cli-anything-geoserver settings fonts

# Workspace-local settings
cli-anything-geoserver settings local-get -w my_workspace
cli-anything-geoserver settings local-create -w my_workspace --param charset=UTF-8
cli-anything-geoserver settings local-update -w my_workspace --param numDecimals=6
cli-anything-geoserver settings local-delete -w my_workspace
```

### `service` — OGC Service Configuration

```bash
cli-anything-geoserver service settings wms
cli-anything-geoserver service settings wfs
cli-anything-geoserver service settings wcs
cli-anything-geoserver service settings wmts
cli-anything-geoserver service settings wms -w my_workspace   # Workspace-specific

cli-anything-geoserver service update wms --param enabled=true --param title="My WMS"
cli-anything-geoserver service update wfs --param maxFeatures=10000
```

### `export` — OGC Data Export & Introspection

#### Map Images (WMS)

```bash
# Export map as PNG
cli-anything-geoserver export map "topp:states" states.png \
  --bbox "-180,-90,180,90" --width 1024 --height 768 --srs EPSG:4326

# Export as JPEG
cli-anything-geoserver export map "topp:states" states.jpg --format image/jpeg

# Export as PDF
cli-anything-geoserver export map "topp:states" states.pdf --format application/pdf

# With specific styles
cli-anything-geoserver export map "topp:states" states.png --styles population

# Multiple layers
cli-anything-geoserver export map "topp:states,topp:roads" composite.png
```

#### Features (WFS)

```bash
# Export as GeoJSON
cli-anything-geoserver export features "topp:states" states.geojson

# Export as CSV
cli-anything-geoserver export features "topp:states" states.csv --format csv

# Export as Shapefile ZIP
cli-anything-geoserver export features "topp:states" states.zip --format "shape-zip"

# With CQL filter
cli-anything-geoserver export features "topp:states" big_states.geojson \
  --cql-filter "PERSONS > 10000000" --max-features 50

# With bounding box filter
cli-anything-geoserver export features "topp:states" west.geojson \
  --bbox "-130,25,-100,50"
```

#### Coverages (WCS)

```bash
cli-anything-geoserver export coverage "nurc:DEM" dem.tif
cli-anything-geoserver export coverage "nurc:DEM" dem.tif --bbox "-180,-90,180,90"
cli-anything-geoserver export coverage "nurc:DEM" dem.png --format image/png
```

#### Capabilities & Introspection

```bash
# Get full capabilities document
cli-anything-geoserver export capabilities wms -o wms_caps.xml
cli-anything-geoserver export capabilities wfs -o wfs_caps.xml
cli-anything-geoserver export capabilities wcs -o wcs_caps.xml

# Get feature info at a point (WMS GetFeatureInfo)
cli-anything-geoserver export featureinfo "topp:states" \
  --bbox "-180,-90,180,90" --width 800 --height 600 --x 400 --y 300

# Get legend graphic
cli-anything-geoserver export legendgraphic "topp:states" legend.png
cli-anything-geoserver export legendgraphic "topp:states" legend.png --style population --width 30 --height 30

# Describe feature type schema
cli-anything-geoserver export describe-featuretype "topp:states" -o schema.json

# Describe coverage
cli-anything-geoserver export describe-coverage "nurc:DEM" -o coverage_desc.xml
```

---

## JSON Output Mode

Every command supports `--json` for machine-readable output, making the CLI suitable for agent consumption and scripting:

```bash
# Pipe JSON output to jq
cli-anything-geoserver --json workspace list | jq '.[].name'
cli-anything-geoserver --json layer list | jq 'length'
cli-anything-geoserver --json style get point | jq '.format'

# Use in shell scripts
LAYERS=$(cli-anything-geoserver --json layer list)
echo "$LAYERS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"
```

## Interactive REPL

Running without a subcommand enters interactive mode with tab completion and history:

```bash
cli-anything-geoserver
# ╭──────────────────────────────────────────────────────╮
# │ ◆  cli-anything · Geoserver                         │
# │    v1.0.0                                            │
# │    Type help for commands, quit to exit              │
# ╰──────────────────────────────────────────────────────╯

# Set workspace context for the session
◆ geoserver ❯ workspace use topp
# ✓ Workspace set to: topp

# Now commands use the workspace context
◆ geoserver [topp] ❯ layer list
◆ geoserver [topp] ❯ store list -w topp
◆ geoserver [topp] ❯ quit
```

## Session Persistence

Save and restore connection state:

```bash
# Save session
cli-anything-geoserver --session my_session.json -w topp workspace list

# Resume session (remembers URL, credentials, workspace)
cli-anything-geoserver --session my_session.json layer list
```

## Architecture

```
cli-anything-geoserver
    ├── REST API (/geoserver/rest/*)
    │   ├── Catalog: workspaces, namespaces, stores, layers, styles, groups
    │   ├── Cascaded: WMS/WMTS stores and layers
    │   ├── Resources: data directory file management
    │   ├── Templates: Freemarker template management
    │   ├── Security: users, groups, roles, access rules, auth config
    │   ├── Settings: global, logging, contact, local workspace
    │   └── System: reload, reset, manifests, fonts
    │
    ├── GeoWebCache (/geoserver/gwc/rest/*)
    │   ├── Tile layers, seed/truncate operations
    │   ├── Grid sets, blob stores, disk quota
    │   └── Global configuration
    │
    └── OGC Services (/geoserver/wms, /wfs, /wcs)
        ├── WMS: GetMap, GetFeatureInfo, GetLegendGraphic, GetCapabilities
        ├── WFS: GetFeature, DescribeFeatureType, GetCapabilities
        └── WCS: GetCoverage, DescribeCoverage, GetCapabilities
```

## Supported Data Sources

| Type | Store Type | Connection Parameters |
|------|-----------|----------------------|
| Shapefile | DataStore | `url=file:data/myshp.shp` |
| PostGIS | DataStore | `host, port, database, user, passwd, dbtype=postgis` |
| GeoTIFF | CoverageStore | `url=file:data/raster.tif` |
| GeoPackage | DataStore | `database=file:data/my.gpkg, dbtype=geopkg` |
| WMS Cascade | WMSStore | `capabilitiesURL=http://...` |
| WMTS Cascade | WMTSStore | `capabilitiesURL=http://...` |

## Output Formats

| Service | Formats |
|---------|---------|
| WMS GetMap | PNG, JPEG, GIF, TIFF, GeoTIFF, PDF, SVG, KML/KMZ |
| WFS GetFeature | GeoJSON, GML 2/3, CSV, Shapefile ZIP, GeoPackage, KML |
| WCS GetCoverage | GeoTIFF, PNG, JPEG, NetCDF |

## Running Tests

```bash
cd agent-harness

# Unit tests (no GeoServer needed)
uv run pytest -v

# E2E tests (requires running GeoServer)
docker run -d --name geoserver -p 8080:8080 docker.io/kartoza/geoserver:latest
uv run pytest cli_anything/geoserver/tests/test_full_e2e.py -v -s

# Force-installed subprocess tests
CLI_ANYTHING_FORCE_INSTALLED=1 uv run pytest -v -s
```
