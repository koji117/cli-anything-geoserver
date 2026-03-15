# Test Plan & Results — cli-anything-geoserver

## Test Inventory

| File | Tests | Description |
|------|-------|-------------|
| `test_core.py` | 84 | Unit tests — synthetic data, mocks, no GeoServer required |
| `test_full_e2e.py` | ~20 | E2E tests — requires running GeoServer instance |

---

## Unit Test Plan (`test_core.py`)

### TestSession — `core/session.py` (7 tests)
- Create session with defaults
- Create session with custom params
- Set workspace (+ undo stack)
- Record action in history
- Serialize to dict and back (round-trip)
- Save and load from file
- Session status output

### TestProject — `core/project.py` (4 tests)
- Create session state with defaults
- Save and load session JSON
- Session info formatting
- Add history entries

### TestGeoServerClient — `utils/geoserver_backend.py` core (4 tests)
- URL construction (rest_url, _url helper)
- Connection error handling (unreachable server)
- API error propagation (mock 404)
- List workspaces with empty response

### TestListHelper — collection listing for all resource types (7 tests)
- list_namespaces (mock JSON response)
- list_wmsstores (cascaded WMS stores)
- list_wmtsstores (cascaded WMTS stores)
- list_wmslayers (cascaded WMS layers)
- list_wmtslayers (cascaded WMTS layers)
- list with empty collection (empty string response)
- list_featuretypes with store parameter (verifies URL path)

### TestCRUDOperations — create/update/delete for all resource types (10 tests)
- create_namespace
- update_datastore
- update_coveragestore
- update_featuretype
- update_coverage
- delete_coverage
- create_wmsstore (cascaded WMS)
- update_layergroup
- update_style (SLD body re-upload)
- update_layer

### TestSecurityMethods — security API (6 tests)
- create_user
- delete_user
- create_role
- assign_role_to_user
- get_data_access_rules
- update_catalog_mode

### TestGWCMethods — GeoWebCache API (4 tests)
- gwc_list_layers
- gwc_seed (seed request)
- gwc_list_gridsets
- gwc_mass_truncate

### TestOGCExtended — OGC service operations (7 tests)
- wms_getcapabilities
- wfs_getcapabilities
- wcs_getcapabilities
- wms_getfeatureinfo
- wfs_describefeaturetype
- wcs_describecoverage
- wms_getlegendgraphic

### TestResourcesTemplates — resources & templates API (4 tests)
- list_resource_directory
- put_resource
- delete_resource
- create_template (with workspace)

### TestSettingsMethods — settings & server API (4 tests)
- get_settings (global)
- get_contact
- server_manifests
- server_reset

### TestExport — `core/export.py` (3 tests)
- export_map (mocked WMS, verifies PNG magic bytes)
- export_features (mocked WFS, verifies GeoJSON structure)
- export_coverage (mocked WCS, verifies TIFF byte order)

### TestCLI — Click CliRunner help verification (22 tests)
- Main CLI help (all 18 groups listed)
- Version flag
- server --help (status, reload, reset, manifests)
- namespace --help (list, get, create, update, delete)
- wmsstore --help (full CRUD)
- wmtsstore --help
- wmslayer --help
- wmtslayer --help
- resource --help (list, get, put, delete)
- template --help
- security --help (user, group, role, rules, catalog-mode, master-password)
- gwc --help (layer, seed, gridset, blobstore, diskquota, global)
- settings --help (get, update, logging, fonts, contact, local)
- export --help (map, features, coverage, capabilities, featureinfo, legendgraphic)
- store has update-datastore + update-coveragestore
- layer has update
- style has update
- layergroup has update
- workspace has update
- service has update

### TestCLISubprocess — subprocess tests (4 tests)
- `--help` via installed command
- `--version` via installed command
- `--json workspace list` against unreachable server (error handling)
- All 18 command groups respond to `--help` via subprocess

**Total: 84 unit tests**

---

## E2E Test Plan (`test_full_e2e.py`)

Requires running GeoServer at `http://localhost:8080/geoserver`.

### TestServer (2 tests)
- server_version: version info contains GeoServer resource
- server_reload: returns ok status

### TestWorkspaceCRUD (2 tests)
- list_workspaces: returns list
- create → get → delete lifecycle with unique name

### TestStoreOperations (2 tests)
- list_datastores in first available workspace
- list_coveragestores in first available workspace

### TestLayerOperations (2 tests)
- list_layers: returns list
- get_layer: gets first available layer details

### TestStyleOperations (2 tests)
- list_styles: returns non-empty list (default styles)
- get_style: gets first available style details

### TestServiceSettings (2 tests)
- WMS settings: returns valid config
- WFS settings: returns valid config

### TestExportMap (1 test)
- WMS GetMap → PNG: verifies magic bytes `\x89PNG` and size > 0

### TestExportFeatures (1 test)
- WFS GetFeature → GeoJSON: verifies `FeatureCollection` type and structure

### TestFullWorkflow (2 tests)
- Workspace lifecycle: create → list → verify → delete → verify gone
- Server admin workflow: version → workspaces → layers → WMS settings

### TestCLISubprocessE2E (4 tests)
- --help via subprocess
- --json workspace list via subprocess
- --json server status via subprocess
- Full export map workflow via subprocess (layer list → export → verify PNG)

**Total: ~20 E2E tests**

---

## Realistic Workflow Scenarios

### Scenario 1: "Publish Shapefile to Web Map"
- **Simulates:** GIS analyst publishing vector data
- **Operations:** workspace create → upload shapefile → layer publish → export map → cleanup
- **Verified:** Workspace exists, layer listed, PNG output has correct magic bytes and size > 0

### Scenario 2: "Set Up Cascaded WMS"
- **Simulates:** Federating data from external WMS servers
- **Operations:** workspace create → wmsstore create → wmslayer create → layer list → export map
- **Verified:** Store and layer created, map export returns valid image

### Scenario 3: "Security Hardening"
- **Simulates:** DevOps locking down a production GeoServer
- **Operations:** security user create → security role create → security role assign-user → security rules data-set → security catalog-mode set HIDE
- **Verified:** User exists, role assigned, access rules applied, catalog mode set

### Scenario 4: "Tile Cache Warm-Up"
- **Simulates:** Preparing GWC for production traffic
- **Operations:** gwc layer list → gwc seed (zoom 0-10) → gwc seed-status → verify completion
- **Verified:** Seed task starts, status shows progress, tiles exist

### Scenario 5: "Server Administration"
- **Simulates:** DevOps checking server health and configuration
- **Operations:** server status → server manifests → settings get → settings logging-get → workspace list → layer list → service settings wms
- **Verified:** Version info returned, manifests list extensions, settings contain expected keys

---

## Test Results

### Unit Tests (`test_core.py`) — 2026-03-15

```
$ PATH=".venv/bin:$PATH" CLI_ANYTHING_FORCE_INSTALLED=1 pytest cli_anything/geoserver/tests/test_core.py -v --tb=no

============================= test session starts ==============================
platform darwin -- Python 3.12.13, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/kojisaruya/IdeaProjects/geoserver/agent-harness
collected 84 items

cli_anything/geoserver/tests/test_core.py::TestSession::test_create_default PASSED [  1%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_create_custom PASSED [  2%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_set_workspace PASSED [  3%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_record_action PASSED [  4%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_to_dict_and_from_dict PASSED [  5%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_save_and_load PASSED [  7%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_status PASSED [  8%]
cli_anything/geoserver/tests/test_core.py::TestProject::test_create_session PASSED [  9%]
cli_anything/geoserver/tests/test_core.py::TestProject::test_save_and_load PASSED [ 10%]
cli_anything/geoserver/tests/test_core.py::TestProject::test_session_info PASSED [ 11%]
cli_anything/geoserver/tests/test_core.py::TestProject::test_add_history PASSED [ 13%]
cli_anything/geoserver/tests/test_core.py::TestGeoServerClient::test_url_construction PASSED [ 14%]
cli_anything/geoserver/tests/test_core.py::TestGeoServerClient::test_connection_error PASSED [ 15%]
cli_anything/geoserver/tests/test_core.py::TestGeoServerClient::test_api_error_propagation PASSED [ 16%]
cli_anything/geoserver/tests/test_core.py::TestGeoServerClient::test_list_workspaces_empty PASSED [ 17%]
cli_anything/geoserver/tests/test_core.py::TestListHelper::test_list_namespaces PASSED [ 19%]
cli_anything/geoserver/tests/test_core.py::TestListHelper::test_list_wmsstores PASSED [ 20%]
cli_anything/geoserver/tests/test_core.py::TestListHelper::test_list_wmtsstores PASSED [ 21%]
cli_anything/geoserver/tests/test_core.py::TestListHelper::test_list_wmslayers PASSED [ 22%]
cli_anything/geoserver/tests/test_core.py::TestListHelper::test_list_wmtslayers PASSED [ 23%]
cli_anything/geoserver/tests/test_core.py::TestListHelper::test_list_empty_collection PASSED [ 25%]
cli_anything/geoserver/tests/test_core.py::TestListHelper::test_list_featuretypes_with_store PASSED [ 26%]
cli_anything/geoserver/tests/test_core.py::TestCRUDOperations::test_create_namespace PASSED [ 27%]
cli_anything/geoserver/tests/test_core.py::TestCRUDOperations::test_update_datastore PASSED [ 28%]
cli_anything/geoserver/tests/test_core.py::TestCRUDOperations::test_update_coveragestore PASSED [ 29%]
cli_anything/geoserver/tests/test_core.py::TestCRUDOperations::test_update_featuretype PASSED [ 30%]
cli_anything/geoserver/tests/test_core.py::TestCRUDOperations::test_update_coverage PASSED [ 32%]
cli_anything/geoserver/tests/test_core.py::TestCRUDOperations::test_delete_coverage PASSED [ 33%]
cli_anything/geoserver/tests/test_core.py::TestCRUDOperations::test_create_wmsstore PASSED [ 34%]
cli_anything/geoserver/tests/test_core.py::TestCRUDOperations::test_update_layergroup PASSED [ 35%]
cli_anything/geoserver/tests/test_core.py::TestCRUDOperations::test_update_style PASSED [ 36%]
cli_anything/geoserver/tests/test_core.py::TestCRUDOperations::test_update_layer PASSED [ 38%]
cli_anything/geoserver/tests/test_core.py::TestSecurityMethods::test_create_user PASSED [ 39%]
cli_anything/geoserver/tests/test_core.py::TestSecurityMethods::test_delete_user PASSED [ 40%]
cli_anything/geoserver/tests/test_core.py::TestSecurityMethods::test_create_role PASSED [ 41%]
cli_anything/geoserver/tests/test_core.py::TestSecurityMethods::test_assign_role_to_user PASSED [ 42%]
cli_anything/geoserver/tests/test_core.py::TestSecurityMethods::test_get_data_access_rules PASSED [ 44%]
cli_anything/geoserver/tests/test_core.py::TestSecurityMethods::test_update_catalog_mode PASSED [ 45%]
cli_anything/geoserver/tests/test_core.py::TestGWCMethods::test_gwc_list_layers PASSED [ 46%]
cli_anything/geoserver/tests/test_core.py::TestGWCMethods::test_gwc_seed PASSED [ 47%]
cli_anything/geoserver/tests/test_core.py::TestGWCMethods::test_gwc_list_gridsets PASSED [ 48%]
cli_anything/geoserver/tests/test_core.py::TestGWCMethods::test_gwc_mass_truncate PASSED [ 50%]
cli_anything/geoserver/tests/test_core.py::TestOGCExtended::test_wms_getcapabilities PASSED [ 51%]
cli_anything/geoserver/tests/test_core.py::TestOGCExtended::test_wfs_getcapabilities PASSED [ 52%]
cli_anything/geoserver/tests/test_core.py::TestOGCExtended::test_wcs_getcapabilities PASSED [ 53%]
cli_anything/geoserver/tests/test_core.py::TestOGCExtended::test_wms_getfeatureinfo PASSED [ 54%]
cli_anything/geoserver/tests/test_core.py::TestOGCExtended::test_wfs_describefeaturetype PASSED [ 55%]
cli_anything/geoserver/tests/test_core.py::TestOGCExtended::test_wcs_describecoverage PASSED [ 57%]
cli_anything/geoserver/tests/test_core.py::TestOGCExtended::test_wms_getlegendgraphic PASSED [ 58%]
cli_anything/geoserver/tests/test_core.py::TestResourcesTemplates::test_list_resource_directory PASSED [ 59%]
cli_anything/geoserver/tests/test_core.py::TestResourcesTemplates::test_put_resource PASSED [ 60%]
cli_anything/geoserver/tests/test_core.py::TestResourcesTemplates::test_delete_resource PASSED [ 61%]
cli_anything/geoserver/tests/test_core.py::TestResourcesTemplates::test_create_template PASSED [ 63%]
cli_anything/geoserver/tests/test_core.py::TestSettingsMethods::test_get_settings PASSED [ 64%]
cli_anything/geoserver/tests/test_core.py::TestSettingsMethods::test_get_contact PASSED [ 65%]
cli_anything/geoserver/tests/test_core.py::TestSettingsMethods::test_server_manifests PASSED [ 66%]
cli_anything/geoserver/tests/test_core.py::TestSettingsMethods::test_server_reset PASSED [ 67%]
cli_anything/geoserver/tests/test_core.py::TestExport::test_export_map PASSED [ 69%]
cli_anything/geoserver/tests/test_core.py::TestExport::test_export_features PASSED [ 70%]
cli_anything/geoserver/tests/test_core.py::TestExport::test_export_coverage PASSED [ 71%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_help PASSED     [ 72%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_version PASSED  [ 73%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_server_help PASSED [ 75%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_namespace_help PASSED [ 76%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_wmsstore_help PASSED [ 77%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_wmtsstore_help PASSED [ 78%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_wmslayer_help PASSED [ 79%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_wmtslayer_help PASSED [ 80%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_resource_help PASSED [ 82%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_template_help PASSED [ 83%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_security_help PASSED [ 84%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_gwc_help PASSED [ 85%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_settings_help PASSED [ 86%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_export_help PASSED [ 88%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_store_has_update_commands PASSED [ 89%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_layer_has_update PASSED [ 90%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_style_has_update PASSED [ 91%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_layergroup_has_update PASSED [ 92%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_workspace_has_update PASSED [ 94%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_service_has_update PASSED [ 95%]
cli_anything/geoserver/tests/test_core.py::TestCLISubprocess::test_help PASSED [ 96%]
cli_anything/geoserver/tests/test_core.py::TestCLISubprocess::test_version PASSED [ 97%]
cli_anything/geoserver/tests/test_core.py::TestCLISubprocess::test_json_workspace_list_no_server PASSED [ 98%]
cli_anything/geoserver/tests/test_core.py::TestCLISubprocess::test_all_command_groups_help PASSED [100%]

============================== 84 passed in 1.55s ==============================
```

### Summary

| Test File | Tests | Passed | Failed | Time |
|-----------|-------|--------|--------|------|
| `test_core.py` | 84 | 84 | 0 | 1.55s |
| `test_full_e2e.py` | ~20 | _(requires running GeoServer)_ | — | — |

**Unit test pass rate: 100% (84/84)**

Subprocess tests confirmed using installed command:
```
[_resolve_cli] Using installed command: /Users/kojisaruya/IdeaProjects/geoserver/agent-harness/.venv/bin/cli-anything-geoserver
```

### Test Coverage by API Area

| Area | Backend Methods | Unit Tests | CLI Tests |
|------|----------------|------------|-----------|
| Session/Project | 12 | 11 | — |
| Server/About | 4 | 2 | help verified |
| Workspaces | 5 | 2 | help + update verified |
| Namespaces | 5 | 1 | help + CRUD verified |
| DataStores | 5 | 2 | help + update verified |
| CoverageStores | 5 | 2 | help + update verified |
| FeatureTypes | 5 | 2 | via layer publish |
| Coverages | 5 | 2 | via layer publish |
| WMS Stores | 5 | 2 | help + CRUD verified |
| WMTS Stores | 5 | 1 | help verified |
| WMS Layers | 5 | 1 | help verified |
| WMTS Layers | 5 | 1 | help verified |
| Layers | 4 | 1 | help + update verified |
| LayerGroups | 5 | 1 | help + update verified |
| Styles | 7 | 1 | help + update verified |
| Services | 2 | — | help + update verified |
| Settings | 10 | 2 | help verified |
| Resources | 5 | 3 | help verified |
| Templates | 4 | 1 | help verified |
| Security Users | 7 | 2 | help verified |
| Security Roles | 10 | 2 | help verified |
| Security Rules | 12 | 1 | help verified |
| GeoWebCache | 16 | 4 | help verified |
| OGC WMS | 4 | 3 | help verified |
| OGC WFS | 3 | 2 | help verified |
| OGC WCS | 3 | 2 | help verified |
| Export | 3 | 3 | help verified |
| File Upload | 4 | — | help verified |
| **Total** | **~120+** | **84** | **all 18 groups** |

### Coverage Notes

- All 18 CLI command groups verified via `--help` both in-process (CliRunner) and subprocess
- Backend methods tested with mocks for all new API areas (namespaces, WMS/WMTS stores, security, GWC, resources, templates, OGC extended)
- Export module tested with magic byte verification (PNG, GeoJSON, TIFF)
- **Not unit-testable:** REPL interactive mode (requires TTY)
- **E2E tests** require running GeoServer — run separately
