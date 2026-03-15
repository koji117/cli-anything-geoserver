# Test Plan — cli-anything-geoserver

## Test Inventory

- `test_core.py`: ~25 unit tests (synthetic data, no GeoServer required)
- `test_full_e2e.py`: ~20 E2E tests (requires running GeoServer instance)

## Unit Test Plan (`test_core.py`)

### Session module (`core/session.py`)
- Create session with defaults
- Create session with custom params
- Set workspace
- Record action in history
- Serialize to dict and back
- Save and load from file
- Session status output
- **Expected:** 7 tests

### Project module (`core/project.py`)
- Create session state
- Save and load session
- Session info formatting
- Add history entries
- **Expected:** 4 tests

### GeoServerClient (`utils/geoserver_backend.py`)
- URL construction
- Connection error handling (no server)
- API error handling (mock 404)
- Request method dispatching
- **Expected:** 4 tests (using unittest.mock)

### Export module (`core/export.py`)
- export_map writes file (mocked WMS)
- export_features writes JSON (mocked WFS)
- export_coverage writes binary (mocked WCS)
- **Expected:** 3 tests (using unittest.mock)

### CLI (`geoserver_cli.py`)
- CLI help output
- Version flag
- JSON mode flag parsing
- **Expected:** 3 tests (Click CliRunner)

### CLI Subprocess (TestCLISubprocess)
- `--help` via subprocess
- `--version` via subprocess
- `--json workspace list` via subprocess (error expected without server)
- **Expected:** 3 tests

**Total unit tests planned: ~24**

## E2E Test Plan (`test_full_e2e.py`)

Requires a running GeoServer instance at `http://localhost:8080/geoserver`.

### Server operations
- Get server version
- Reload catalog

### Workspace CRUD
- Create workspace → verify exists → delete

### Store CRUD
- Create datastore → list → delete
- Upload shapefile (if test data available)

### Layer operations
- List layers
- Get layer details (using default sample data)

### Style operations
- List styles
- Get style details (built-in styles like "point", "line", "polygon")
- Get SLD body

### Export workflows
- Export map image via WMS GetMap → verify PNG magic bytes
- Export features via WFS GetFeature → verify GeoJSON structure
- Full workflow: create workspace → upload data → export map → cleanup

**Total E2E tests planned: ~15**

## Realistic Workflow Scenarios

### Scenario 1: "Publish Shapefile to Web Map"
- **Simulates:** GIS analyst publishing vector data
- **Operations:** workspace create → upload shapefile → layer publish → export map → cleanup
- **Verified:** Workspace exists, layer listed, PNG output has correct magic bytes and size > 0

### Scenario 2: "Configure and Export"
- **Simulates:** Agent setting up GeoServer and downloading data
- **Operations:** workspace create → list styles → export features as GeoJSON → verify JSON structure
- **Verified:** GeoJSON has "type": "FeatureCollection", features array exists

### Scenario 3: "Server Administration"
- **Simulates:** DevOps checking server health
- **Operations:** server status → list workspaces → list layers → service settings wms
- **Verified:** Version info returned, workspace list is array, WMS settings contain expected keys

---

## Test Results

### Unit Tests (`test_core.py`) — 2026-03-15

```
$ CLI_ANYTHING_FORCE_INSTALLED=1 pytest cli_anything/geoserver/tests/test_core.py -v --tb=no

============================= test session starts ==============================
platform darwin -- Python 3.12.13, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/kojisaruya/IdeaProjects/geoserver/agent-harness
collected 24 items

cli_anything/geoserver/tests/test_core.py::TestSession::test_create_default PASSED [  4%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_create_custom PASSED [  8%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_set_workspace PASSED [ 12%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_record_action PASSED [ 16%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_to_dict_and_from_dict PASSED [ 20%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_save_and_load PASSED [ 25%]
cli_anything/geoserver/tests/test_core.py::TestSession::test_status PASSED [ 29%]
cli_anything/geoserver/tests/test_core.py::TestProject::test_create_session PASSED [ 33%]
cli_anything/geoserver/tests/test_core.py::TestProject::test_save_and_load PASSED [ 37%]
cli_anything/geoserver/tests/test_core.py::TestProject::test_session_info PASSED [ 41%]
cli_anything/geoserver/tests/test_core.py::TestProject::test_add_history PASSED [ 45%]
cli_anything/geoserver/tests/test_core.py::TestGeoServerClient::test_url_construction PASSED [ 50%]
cli_anything/geoserver/tests/test_core.py::TestGeoServerClient::test_connection_error PASSED [ 54%]
cli_anything/geoserver/tests/test_core.py::TestGeoServerClient::test_api_error_propagation PASSED [ 58%]
cli_anything/geoserver/tests/test_core.py::TestGeoServerClient::test_list_workspaces_empty PASSED [ 62%]
cli_anything/geoserver/tests/test_core.py::TestExport::test_export_map PASSED [ 66%]
cli_anything/geoserver/tests/test_core.py::TestExport::test_export_features PASSED [ 70%]
cli_anything/geoserver/tests/test_core.py::TestExport::test_export_coverage PASSED [ 75%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_help PASSED     [ 79%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_version PASSED  [ 83%]
cli_anything/geoserver/tests/test_core.py::TestCLI::test_server_help PASSED [ 87%]
cli_anything/geoserver/tests/test_core.py::TestCLISubprocess::test_help PASSED [ 91%]
cli_anything/geoserver/tests/test_core.py::TestCLISubprocess::test_version PASSED [ 95%]
cli_anything/geoserver/tests/test_core.py::TestCLISubprocess::test_json_workspace_list_no_server PASSED [100%]

============================== 24 passed in 0.28s ==============================
```

### Summary

| Test File | Tests | Passed | Failed | Time |
|-----------|-------|--------|--------|------|
| `test_core.py` | 24 | 24 | 0 | 0.28s |
| `test_full_e2e.py` | 18 | _(requires running GeoServer)_ | — | — |

**Unit test pass rate: 100% (24/24)**

Subprocess tests confirmed using installed command:
```
[_resolve_cli] Using installed command: /Users/kojisaruya/IdeaProjects/geoserver/agent-harness/.venv/bin/cli-anything-geoserver
```

### Coverage Notes

- **Unit tests** cover all core modules (session, project, backend client, export, CLI) with synthetic data and mocks
- **E2E tests** require a running GeoServer instance — run separately with `docker run -d --name geoserver -p 8080:8080 docker.io/kartoza/geoserver:latest`
- **Not covered:** REPL interactive mode (requires TTY), style SLD upload (requires real server), GeoWebCache tile operations
