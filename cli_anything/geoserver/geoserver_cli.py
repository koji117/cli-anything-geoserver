"""GeoServer CLI — command-line interface for GeoServer geospatial server."""

import json as json_mod
import os
import sys
import shlex

import click

from cli_anything.geoserver.utils.geoserver_backend import GeoServerClient, GeoServerError
from cli_anything.geoserver.core.session import Session


# ── Helpers ──────────────────────────────────────────────────────────────

def _output(ctx, data, human_fn=None):
    """Output data as JSON or human-readable."""
    if ctx.obj.get("json_mode"):
        click.echo(json_mod.dumps(data, indent=2, default=str))
    elif human_fn:
        human_fn(data)
    else:
        click.echo(json_mod.dumps(data, indent=2, default=str))


def _get_client(ctx):
    """Get GeoServerClient from context."""
    return ctx.obj["client"]


def _handle_error(ctx, e):
    """Handle GeoServerError."""
    if ctx.obj.get("json_mode"):
        click.echo(json_mod.dumps({
            "error": str(e),
            "status_code": getattr(e, "status_code", None),
        }), err=True)
    else:
        click.echo(f"Error: {e}", err=True)
        if hasattr(e, "response_text") and e.response_text:
            click.echo(f"  Response: {e.response_text[:200]}", err=True)
    ctx.exit(1)


# ── Main CLI Group ───────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--url", envvar="GEOSERVER_URL", default="http://localhost:8080/geoserver",
              help="GeoServer base URL")
@click.option("--user", envvar="GEOSERVER_USER", default="admin", help="Username")
@click.option("--password", envvar="GEOSERVER_PASSWORD", default="geoserver", help="Password")
@click.option("--workspace", "-w", default=None, help="Default workspace context")
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON")
@click.option("--session", "session_path", default=None, help="Session file path")
@click.version_option(version="1.0.0", prog_name="cli-anything-geoserver")
@click.pass_context
def cli(ctx, url, user, password, workspace, json_mode, session_path):
    """CLI harness for GeoServer geospatial server.

    Manages workspaces, data stores, layers, styles, and exports via
    GeoServer's REST API and OGC services.
    """
    ctx.ensure_object(dict)

    # Load session if provided
    if session_path and os.path.exists(session_path):
        sess = Session.load(session_path)
        url = url if url != "http://localhost:8080/geoserver" else sess.url
        user = user if user != "admin" else sess.username
        password = password if password != "geoserver" else sess.password
        workspace = workspace or sess.workspace
    else:
        sess = Session(url=url, username=user, password=password)

    if workspace:
        sess.set_workspace(workspace)

    ctx.obj["client"] = GeoServerClient(url=url, username=user, password=password)
    ctx.obj["json_mode"] = json_mode
    ctx.obj["session"] = sess
    ctx.obj["session_path"] = session_path
    ctx.obj["workspace"] = workspace

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── REPL ─────────────────────────────────────────────────────────────────

@cli.command(hidden=True)
@click.pass_context
def repl(ctx):
    """Interactive REPL mode."""
    from cli_anything.geoserver.utils.repl_skin import ReplSkin

    skin = ReplSkin("geoserver", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()
    ws = ctx.obj.get("workspace", "")

    commands_help = {
        "server status": "Show server status and version",
        "server reload": "Reload the GeoServer catalog",
        "workspace list": "List all workspaces",
        "workspace create <name>": "Create a new workspace",
        "workspace get <name>": "Get workspace details",
        "workspace delete <name>": "Delete a workspace",
        "workspace use <name>": "Set current workspace context",
        "store list [--workspace WS]": "List data stores",
        "store create <name> ...": "Create a data store",
        "store get <name>": "Get store details",
        "store delete <name>": "Delete a store",
        "layer list": "List all layers",
        "layer get <name>": "Get layer details",
        "layer delete <name>": "Delete a layer",
        "style list": "List all styles",
        "style get <name>": "Get style details",
        "style create <name> <sld-file>": "Create a style from SLD file",
        "style delete <name>": "Delete a style",
        "layergroup list": "List layer groups",
        "layergroup get <name>": "Get layer group details",
        "service settings <wms|wfs|wcs>": "Get service settings",
        "export map <layers> <output>": "Export map image via WMS",
        "export features <typenames> <output>": "Export features via WFS",
        "export coverage <id> <output>": "Export coverage via WCS",
        "status": "Show session status",
        "help": "Show this help",
        "quit / exit": "Exit the REPL",
    }

    while True:
        try:
            line = skin.get_input(pt_session, project_name=ws or "", modified=False)
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue

        if line in ("quit", "exit", "q"):
            # Save session if path was specified
            if ctx.obj.get("session_path"):
                ctx.obj["session"].save(ctx.obj["session_path"])
            skin.print_goodbye()
            break

        if line == "help":
            skin.help(commands_help)
            continue

        if line == "status":
            info = ctx.obj["session"].status()
            for k, v in info.items():
                skin.status(k, str(v))
            continue

        if line.startswith("workspace use "):
            ws_name = line.split("workspace use ", 1)[1].strip()
            ctx.obj["workspace"] = ws_name
            ctx.obj["session"].set_workspace(ws_name)
            ws = ws_name
            skin.success(f"Workspace set to: {ws_name}")
            continue

        # Dispatch to Click commands
        try:
            args = shlex.split(line)
            # Inject workspace if set
            if ws and "--workspace" not in args and "-w" not in args:
                # Only for commands that support workspace
                pass
            cli.main(args=args, ctx=ctx, standalone_mode=False)
        except SystemExit:
            pass
        except GeoServerError as e:
            skin.error(str(e))
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(f"Unexpected error: {e}")


# ── Server Commands ──────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def server(ctx):
    """Server management commands."""
    pass


@server.command("status")
@click.pass_context
def server_status(ctx):
    """Show GeoServer server status."""
    try:
        client = _get_client(ctx)
        version = client.server_version()
        _output(ctx, version, lambda d: _print_server_info(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


def _print_server_info(data):
    about = data.get("about", {})
    resources = about.get("resource", [])
    for r in resources:
        if r.get("@name") == "GeoServer":
            click.echo(f"GeoServer Version: {r.get('Version', 'unknown')}")
            click.echo(f"Build Timestamp:   {r.get('Build-Timestamp', 'unknown')}")
            click.echo(f"Git Revision:      {r.get('Git-Revision', 'unknown')[:12]}")
            break


@server.command("reload")
@click.pass_context
def server_reload(ctx):
    """Reload the GeoServer catalog."""
    try:
        client = _get_client(ctx)
        result = client.server_reload()
        _output(ctx, result, lambda d: click.echo("Catalog reloaded successfully."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Workspace Commands ───────────────────────────────────────────────────

@cli.group()
@click.pass_context
def workspace(ctx):
    """Workspace management commands."""
    pass


@workspace.command("list")
@click.pass_context
def workspace_list(ctx):
    """List all workspaces."""
    try:
        client = _get_client(ctx)
        workspaces = client.list_workspaces()
        _output(ctx, workspaces, lambda d: _print_workspace_list(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


def _print_workspace_list(workspaces):
    if not workspaces:
        click.echo("No workspaces found.")
        return
    click.echo(f"{'Name':<30} {'Href'}")
    click.echo("-" * 60)
    for ws in workspaces:
        name = ws.get("name", "") if isinstance(ws, dict) else str(ws)
        click.echo(f"{name:<30}")


@workspace.command("create")
@click.argument("name")
@click.option("--isolated", is_flag=True, help="Create as isolated workspace")
@click.pass_context
def workspace_create(ctx, name, isolated):
    """Create a new workspace."""
    try:
        client = _get_client(ctx)
        result = client.create_workspace(name, isolated=isolated)
        _output(ctx, result, lambda d: click.echo(f"Workspace '{name}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@workspace.command("get")
@click.argument("name")
@click.pass_context
def workspace_get(ctx, name):
    """Get workspace details."""
    try:
        client = _get_client(ctx)
        ws = client.get_workspace(name)
        _output(ctx, ws, lambda d: _print_workspace_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


def _print_workspace_detail(ws):
    for k, v in ws.items():
        if not k.startswith("@"):
            click.echo(f"  {k}: {v}")


@workspace.command("delete")
@click.argument("name")
@click.option("--recurse", is_flag=True, help="Recursively delete all contents")
@click.pass_context
def workspace_delete(ctx, name, recurse):
    """Delete a workspace."""
    try:
        client = _get_client(ctx)
        result = client.delete_workspace(name, recurse=recurse)
        _output(ctx, result, lambda d: click.echo(f"Workspace '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Store Commands ───────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def store(ctx):
    """Data store management commands."""
    pass


@store.command("list")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--type", "store_type", type=click.Choice(["data", "coverage", "all"]),
              default="all", help="Store type filter")
@click.pass_context
def store_list(ctx, workspace, store_type):
    """List data stores in a workspace."""
    try:
        client = _get_client(ctx)
        results = []
        if store_type in ("data", "all"):
            ds = client.list_datastores(workspace)
            for d in ds:
                if isinstance(d, dict):
                    d["store_type"] = "datastore"
                results.extend(ds)
        if store_type in ("coverage", "all"):
            cs = client.list_coveragestores(workspace)
            for c in cs:
                if isinstance(c, dict):
                    c["store_type"] = "coveragestore"
                results.extend(cs)
        _output(ctx, results, lambda d: _print_store_list(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


def _print_store_list(stores):
    if not stores:
        click.echo("No stores found.")
        return
    click.echo(f"{'Name':<25} {'Type':<15}")
    click.echo("-" * 40)
    for s in stores:
        name = s.get("name", "") if isinstance(s, dict) else str(s)
        stype = s.get("store_type", "unknown") if isinstance(s, dict) else ""
        click.echo(f"{name:<25} {stype:<15}")


@store.command("get")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--type", "store_type", type=click.Choice(["data", "coverage"]),
              default="data", help="Store type")
@click.pass_context
def store_get(ctx, name, workspace, store_type):
    """Get store details."""
    try:
        client = _get_client(ctx)
        if store_type == "data":
            data = client.get_datastore(workspace, name)
        else:
            data = client.get_coveragestore(workspace, name)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@store.command("create-datastore")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--param", "-p", multiple=True, help="Connection param as key=value")
@click.pass_context
def store_create_datastore(ctx, name, workspace, param):
    """Create a new data store."""
    try:
        client = _get_client(ctx)
        params = {}
        for p in param:
            k, v = p.split("=", 1)
            params[k] = v
        result = client.create_datastore(workspace, name, params)
        _output(ctx, result, lambda d: click.echo(f"Data store '{name}' created in '{workspace}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@store.command("create-coveragestore")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--url", required=True, help="Coverage URL (e.g., file:data/raster.tif)")
@click.option("--type", "store_type", default="GeoTIFF", help="Coverage store type")
@click.pass_context
def store_create_coveragestore(ctx, name, workspace, url, store_type):
    """Create a new coverage store."""
    try:
        client = _get_client(ctx)
        result = client.create_coveragestore(workspace, name, url, store_type=store_type)
        _output(ctx, result, lambda d: click.echo(f"Coverage store '{name}' created in '{workspace}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@store.command("delete")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--type", "store_type", type=click.Choice(["data", "coverage"]),
              default="data", help="Store type")
@click.option("--recurse", is_flag=True, help="Recursively delete contents")
@click.pass_context
def store_delete(ctx, name, workspace, store_type, recurse):
    """Delete a data store."""
    try:
        client = _get_client(ctx)
        if store_type == "data":
            result = client.delete_datastore(workspace, name, recurse=recurse)
        else:
            result = client.delete_coveragestore(workspace, name, recurse=recurse)
        _output(ctx, result, lambda d: click.echo(f"Store '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@store.command("upload-shapefile")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--file", "file_path", required=True, type=click.Path(exists=True),
              help="Path to zipped shapefile")
@click.pass_context
def store_upload_shapefile(ctx, name, workspace, file_path):
    """Upload a zipped shapefile to create a data store."""
    try:
        client = _get_client(ctx)
        result = client.upload_shapefile(workspace, name, file_path)
        _output(ctx, result, lambda d: click.echo(f"Shapefile uploaded as store '{name}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@store.command("upload-geotiff")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--file", "file_path", required=True, type=click.Path(exists=True),
              help="Path to GeoTIFF file")
@click.pass_context
def store_upload_geotiff(ctx, name, workspace, file_path):
    """Upload a GeoTIFF to create a coverage store."""
    try:
        client = _get_client(ctx)
        result = client.upload_geotiff(workspace, name, file_path)
        _output(ctx, result, lambda d: click.echo(f"GeoTIFF uploaded as store '{name}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Layer Commands ───────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def layer(ctx):
    """Layer management commands."""
    pass


@layer.command("list")
@click.option("--workspace", "-w", default=None, help="Filter by workspace")
@click.pass_context
def layer_list(ctx, workspace):
    """List all layers."""
    try:
        client = _get_client(ctx)
        workspace = workspace or ctx.obj.get("workspace")
        layers = client.list_layers(workspace=workspace)
        _output(ctx, layers, lambda d: _print_layer_list(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


def _print_layer_list(layers):
    if not layers:
        click.echo("No layers found.")
        return
    click.echo(f"{'Name':<40}")
    click.echo("-" * 40)
    for l in layers:
        name = l.get("name", "") if isinstance(l, dict) else str(l)
        click.echo(f"{name:<40}")


@layer.command("get")
@click.argument("name")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.pass_context
def layer_get(ctx, name, workspace):
    """Get layer details."""
    try:
        client = _get_client(ctx)
        workspace = workspace or ctx.obj.get("workspace")
        data = client.get_layer(name, workspace=workspace)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@layer.command("delete")
@click.argument("name")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.option("--recurse", is_flag=True, help="Recursively delete")
@click.pass_context
def layer_delete(ctx, name, workspace, recurse):
    """Delete a layer."""
    try:
        client = _get_client(ctx)
        workspace = workspace or ctx.obj.get("workspace")
        result = client.delete_layer(name, workspace=workspace, recurse=recurse)
        _output(ctx, result, lambda d: click.echo(f"Layer '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@layer.command("publish")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--store", "-s", required=True, help="Store name")
@click.option("--type", "layer_type", type=click.Choice(["feature", "coverage"]),
              default="feature", help="Layer type")
@click.pass_context
def layer_publish(ctx, name, workspace, store, layer_type):
    """Publish a resource as a layer."""
    try:
        client = _get_client(ctx)
        if layer_type == "feature":
            result = client.create_featuretype(workspace, store, name)
        else:
            result = client.create_coverage(workspace, store, name)
        _output(ctx, result, lambda d: click.echo(f"Layer '{name}' published."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Style Commands ───────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def style(ctx):
    """Style management commands."""
    pass


@style.command("list")
@click.option("--workspace", "-w", default=None, help="Filter by workspace")
@click.pass_context
def style_list(ctx, workspace):
    """List all styles."""
    try:
        client = _get_client(ctx)
        styles = client.list_styles(workspace=workspace)
        _output(ctx, styles, lambda d: _print_style_list(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


def _print_style_list(styles):
    if not styles:
        click.echo("No styles found.")
        return
    click.echo(f"{'Name':<30} {'Format':<15}")
    click.echo("-" * 45)
    for s in styles:
        name = s.get("name", "") if isinstance(s, dict) else str(s)
        fmt = s.get("format", "") if isinstance(s, dict) else ""
        click.echo(f"{name:<30} {fmt:<15}")


@style.command("get")
@click.argument("name")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.option("--body", is_flag=True, help="Get the SLD body")
@click.pass_context
def style_get(ctx, name, workspace, body):
    """Get style details or SLD body."""
    try:
        client = _get_client(ctx)
        if body:
            sld = client.get_style_body(name, workspace=workspace)
            click.echo(sld)
        else:
            data = client.get_style(name, workspace=workspace)
            _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@style.command("create")
@click.argument("name")
@click.option("--file", "sld_file", required=True, type=click.Path(exists=True),
              help="Path to SLD file")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.pass_context
def style_create(ctx, name, sld_file, workspace):
    """Create a style from an SLD file."""
    try:
        client = _get_client(ctx)
        with open(sld_file, "r") as f:
            sld_body = f.read()
        result = client.create_style(name, sld_body, workspace=workspace)
        _output(ctx, result, lambda d: click.echo(f"Style '{name}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@style.command("delete")
@click.argument("name")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.option("--purge", is_flag=True, help="Also delete the style file")
@click.pass_context
def style_delete(ctx, name, workspace, purge):
    """Delete a style."""
    try:
        client = _get_client(ctx)
        result = client.delete_style(name, workspace=workspace, purge=purge)
        _output(ctx, result, lambda d: click.echo(f"Style '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Layer Group Commands ─────────────────────────────────────────────────

@cli.group()
@click.pass_context
def layergroup(ctx):
    """Layer group management commands."""
    pass


@layergroup.command("list")
@click.option("--workspace", "-w", default=None, help="Filter by workspace")
@click.pass_context
def layergroup_list(ctx, workspace):
    """List layer groups."""
    try:
        client = _get_client(ctx)
        groups = client.list_layergroups(workspace=workspace)
        _output(ctx, groups, lambda d: _print_list_names(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@layergroup.command("get")
@click.argument("name")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.pass_context
def layergroup_get(ctx, name, workspace):
    """Get layer group details."""
    try:
        client = _get_client(ctx)
        data = client.get_layergroup(name, workspace=workspace)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@layergroup.command("create")
@click.argument("name")
@click.option("--layer", "-l", multiple=True, required=True, help="Layer name (repeatable)")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.pass_context
def layergroup_create(ctx, name, layer, workspace):
    """Create a layer group."""
    try:
        client = _get_client(ctx)
        result = client.create_layergroup(name, list(layer), workspace=workspace)
        _output(ctx, result, lambda d: click.echo(f"Layer group '{name}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@layergroup.command("delete")
@click.argument("name")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.pass_context
def layergroup_delete(ctx, name, workspace):
    """Delete a layer group."""
    try:
        client = _get_client(ctx)
        result = client.delete_layergroup(name, workspace=workspace)
        _output(ctx, result, lambda d: click.echo(f"Layer group '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Service Commands ─────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def service(ctx):
    """OGC service configuration commands."""
    pass


@service.command("settings")
@click.argument("service_name", type=click.Choice(["wms", "wfs", "wcs", "wmts"]))
@click.option("--workspace", "-w", default=None, help="Workspace-specific settings")
@click.pass_context
def service_settings(ctx, service_name, workspace):
    """Get OGC service settings."""
    try:
        client = _get_client(ctx)
        data = client.get_service_settings(service_name, workspace=workspace)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Export Commands ──────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def export(ctx):
    """Export maps, features, and coverages."""
    pass


@export.command("map")
@click.argument("layers")
@click.argument("output")
@click.option("--bbox", default="-180,-90,180,90", help="Bounding box: minx,miny,maxx,maxy")
@click.option("--width", default=800, help="Image width")
@click.option("--height", default=600, help="Image height")
@click.option("--srs", default="EPSG:4326", help="Spatial reference system")
@click.option("--format", "fmt", default="image/png", help="Output format")
@click.option("--styles", default="", help="Style names (comma-separated)")
@click.pass_context
def export_map_cmd(ctx, layers, output, bbox, width, height, srs, fmt, styles):
    """Export a map image via WMS GetMap."""
    try:
        from cli_anything.geoserver.core.export import export_map
        client = _get_client(ctx)
        result = export_map(client, layers, output, bbox=bbox, width=width,
                           height=height, srs=srs, format=fmt, styles=styles)
        _output(ctx, result, lambda d: click.echo(
            f"Map exported: {d['output']} ({d['file_size']:,} bytes)"))
    except GeoServerError as e:
        _handle_error(ctx, e)


@export.command("features")
@click.argument("typenames")
@click.argument("output")
@click.option("--format", "fmt", default="application/json", help="Output format")
@click.option("--max-features", type=int, default=None, help="Max features")
@click.option("--cql-filter", default=None, help="CQL filter expression")
@click.option("--bbox", default=None, help="Bounding box filter")
@click.option("--srs", default="EPSG:4326", help="Spatial reference system")
@click.pass_context
def export_features_cmd(ctx, typenames, output, fmt, max_features, cql_filter, bbox, srs):
    """Export features via WFS GetFeature."""
    try:
        from cli_anything.geoserver.core.export import export_features
        client = _get_client(ctx)
        result = export_features(client, typenames, output, format=fmt,
                                max_features=max_features, cql_filter=cql_filter,
                                bbox=bbox, srs=srs)
        _output(ctx, result, lambda d: click.echo(
            f"Features exported: {d['output']} ({d['file_size']:,} bytes)"))
    except GeoServerError as e:
        _handle_error(ctx, e)


@export.command("coverage")
@click.argument("coverage_id")
@click.argument("output")
@click.option("--format", "fmt", default="image/tiff", help="Output format")
@click.option("--bbox", default=None, help="Bounding box")
@click.option("--srs", default="EPSG:4326", help="Spatial reference system")
@click.pass_context
def export_coverage_cmd(ctx, coverage_id, output, fmt, bbox, srs):
    """Export raster coverage via WCS GetCoverage."""
    try:
        from cli_anything.geoserver.core.export import export_coverage
        client = _get_client(ctx)
        result = export_coverage(client, coverage_id, output, format=fmt,
                                bbox=bbox, srs=srs)
        _output(ctx, result, lambda d: click.echo(
            f"Coverage exported: {d['output']} ({d['file_size']:,} bytes)"))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Shared display helpers ───────────────────────────────────────────────

def _print_detail(data):
    """Print a dict as key-value pairs."""
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                click.echo(f"  {k}:")
                for k2, v2 in v.items():
                    click.echo(f"    {k2}: {v2}")
            elif isinstance(v, list):
                click.echo(f"  {k}: [{len(v)} items]")
            else:
                click.echo(f"  {k}: {v}")
    else:
        click.echo(str(data))


def _print_list_names(items):
    """Print a list of items by name."""
    if not items:
        click.echo("No items found.")
        return
    for item in items:
        name = item.get("name", str(item)) if isinstance(item, dict) else str(item)
        click.echo(f"  {name}")


# ── Entry point ──────────────────────────────────────────────────────────

def main():
    cli(auto_envvar_prefix="GEOSERVER")


if __name__ == "__main__":
    main()
