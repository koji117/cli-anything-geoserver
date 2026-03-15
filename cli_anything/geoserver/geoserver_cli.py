"""GeoServer CLI — command-line interface for GeoServer geospatial server."""

import json as json_mod
import os
import shlex

import click

from cli_anything.geoserver.core.session import Session
from cli_anything.geoserver.utils.geoserver_backend import GeoServerClient, GeoServerError

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
        click.echo(
            json_mod.dumps(
                {
                    "error": str(e),
                    "status_code": getattr(e, "status_code", None),
                }
            ),
            err=True,
        )
    else:
        click.echo(f"Error: {e}", err=True)
        if hasattr(e, "response_text") and e.response_text:
            click.echo(f"  Response: {e.response_text[:200]}", err=True)
    ctx.exit(1)


# ── Main CLI Group ───────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.option("--url", envvar="GEOSERVER_URL", default="http://localhost:8080/geoserver", help="GeoServer base URL")
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
        "server reset": "Reset GeoServer resource/memory caches",
        "server manifests": "Show GeoServer manifests",
        "workspace list": "List all workspaces",
        "workspace create <name>": "Create a new workspace",
        "workspace get <name>": "Get workspace details",
        "workspace update <name>": "Update workspace settings",
        "workspace delete <name>": "Delete a workspace",
        "workspace use <name>": "Set current workspace context",
        "namespace list": "List all namespaces",
        "namespace get <prefix>": "Get namespace details",
        "namespace create <prefix> <uri>": "Create a namespace",
        "namespace update <prefix>": "Update a namespace URI",
        "namespace delete <prefix>": "Delete a namespace",
        "store list [--workspace WS]": "List data stores",
        "store create-datastore <name> ...": "Create a data store",
        "store create-coveragestore <name> ...": "Create a coverage store",
        "store get <name>": "Get store details",
        "store update-datastore <name>": "Update a data store",
        "store update-coveragestore <name>": "Update a coverage store",
        "store delete <name>": "Delete a store",
        "wmsstore list -w <ws>": "List cascaded WMS stores",
        "wmsstore get <name> -w <ws>": "Get WMS store details",
        "wmsstore create <name> -w <ws> --url <cap>": "Create a WMS store",
        "wmsstore update <name> -w <ws>": "Update a WMS store",
        "wmsstore delete <name> -w <ws>": "Delete a WMS store",
        "wmtsstore list -w <ws>": "List cascaded WMTS stores",
        "wmtsstore get <name> -w <ws>": "Get WMTS store details",
        "wmtsstore create <name> -w <ws> --url <cap>": "Create a WMTS store",
        "wmtsstore update <name> -w <ws>": "Update a WMTS store",
        "wmtsstore delete <name> -w <ws>": "Delete a WMTS store",
        "wmslayer list -w <ws>": "List cascaded WMS layers",
        "wmslayer get <name> -w <ws> -s <store>": "Get WMS layer details",
        "wmslayer create <name> -w <ws> -s <store>": "Create a WMS layer",
        "wmslayer update <name> -w <ws> -s <store>": "Update a WMS layer",
        "wmslayer delete <name> -w <ws> -s <store>": "Delete a WMS layer",
        "wmtslayer list -w <ws>": "List cascaded WMTS layers",
        "wmtslayer get <name> -w <ws> -s <store>": "Get WMTS layer details",
        "wmtslayer create <name> -w <ws> -s <store>": "Create a WMTS layer",
        "wmtslayer update <name> -w <ws> -s <store>": "Update a WMTS layer",
        "wmtslayer delete <name> -w <ws> -s <store>": "Delete a WMTS layer",
        "layer list": "List all layers",
        "layer get <name>": "Get layer details",
        "layer update <name>": "Update layer settings",
        "layer delete <name>": "Delete a layer",
        "style list": "List all styles",
        "style get <name>": "Get style details",
        "style create <name> --file <sld>": "Create a style from SLD file",
        "style update <name> --file <sld>": "Update a style from SLD file",
        "style delete <name>": "Delete a style",
        "layergroup list": "List layer groups",
        "layergroup get <name>": "Get layer group details",
        "layergroup create <name> -l <layer>": "Create a layer group",
        "layergroup update <name>": "Update a layer group",
        "layergroup delete <name>": "Delete a layer group",
        "resource list [path]": "List data directory contents",
        "resource get <path>": "Get a resource file",
        "resource put <path> --file <file>": "Upload a resource file",
        "resource delete <path>": "Delete a resource file",
        "template list": "List Freemarker templates",
        "template get <name>": "Get template body",
        "template create <name> --file <file>": "Create/upload a template",
        "template delete <name>": "Delete a template",
        "security user list": "List security users",
        "security user get <name>": "Get user details",
        "security user create <name> --password <pw>": "Create a user",
        "security user update <name>": "Update a user",
        "security user delete <name>": "Delete a user",
        "security group list": "List user groups",
        "security group create <name>": "Create a user group",
        "security group delete <name>": "Delete a user group",
        "security role list": "List roles",
        "security role create <name>": "Create a role",
        "security role delete <name>": "Delete a role",
        "security role assign-user <role> <user>": "Assign role to user",
        "security role remove-user <role> <user>": "Remove role from user",
        "security role assign-group <role> <group>": "Assign role to group",
        "security role remove-group <role> <group>": "Remove role from group",
        "security rules data": "Get/set data access rules",
        "security rules service": "Get/set service access rules",
        "security rules rest": "Get/set REST access rules",
        "security catalog-mode get": "Get catalog mode",
        "security catalog-mode set <mode>": "Set catalog mode",
        "security master-password get": "Get master password info",
        "security master-password update": "Update master password",
        "security auth-filters list": "List auth filters",
        "security auth-filters get <name>": "Get auth filter details",
        "security auth-providers list": "List auth providers",
        "security auth-providers get <name>": "Get auth provider details",
        "service settings <wms|wfs|wcs|wmts>": "Get service settings",
        "service update <wms|wfs|wcs|wmts>": "Update service settings",
        "settings get": "Get global settings",
        "settings update": "Update global settings",
        "settings logging-get": "Get logging settings",
        "settings logging-update": "Update logging settings",
        "settings contact-get": "Get contact info",
        "settings contact-update": "Update contact info",
        "settings fonts": "List available fonts",
        "settings local-get <ws>": "Get workspace-local settings",
        "settings local-create <ws>": "Create workspace-local settings",
        "settings local-update <ws>": "Update workspace-local settings",
        "settings local-delete <ws>": "Delete workspace-local settings",
        "gwc layer list": "List GWC tile layers",
        "gwc layer get <name>": "Get GWC layer config",
        "gwc layer update <name>": "Update GWC layer config",
        "gwc layer delete <name>": "Delete GWC layer",
        "gwc seed <layer>": "Seed/reseed/truncate tiles",
        "gwc seed-status [layer]": "Check seed task status",
        "gwc terminate [layer]": "Terminate seed tasks",
        "gwc mass-truncate": "Mass truncate tiles",
        "gwc gridset list": "List GWC grid sets",
        "gwc gridset get <name>": "Get grid set details",
        "gwc gridset create <name>": "Create a grid set",
        "gwc gridset delete <name>": "Delete a grid set",
        "gwc blobstore list": "List GWC blob stores",
        "gwc blobstore get <name>": "Get blob store details",
        "gwc blobstore create <name>": "Create a blob store",
        "gwc blobstore delete <name>": "Delete a blob store",
        "gwc diskquota get": "Get GWC disk quota config",
        "gwc diskquota update": "Update GWC disk quota config",
        "gwc global get": "Get GWC global config",
        "gwc global update": "Update GWC global config",
        "export map <layers> <output>": "Export map image via WMS",
        "export features <typenames> <output>": "Export features via WFS",
        "export coverage <id> <output>": "Export coverage via WCS",
        "export capabilities <service>": "Get OGC capabilities document",
        "export featureinfo <layers> <output>": "Get feature info via WMS",
        "export legendgraphic <layer> <output>": "Get legend graphic via WMS",
        "export describe-featuretype <typenames>": "Describe feature type via WFS",
        "export describe-coverage <coverage-id>": "Describe coverage via WCS",
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


@server.command("reset")
@click.pass_context
def server_reset(ctx):
    """Reset GeoServer resource and memory caches."""
    try:
        client = _get_client(ctx)
        result = client.server_reset()
        _output(ctx, result, lambda d: click.echo("Catalog reset successfully."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@server.command("manifests")
@click.pass_context
def server_manifests(ctx):
    """Show GeoServer manifests (installed modules)."""
    try:
        client = _get_client(ctx)
        data = client.server_manifests()
        _output(ctx, data, lambda d: _print_detail(d))
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


@workspace.command("update")
@click.argument("name")
@click.option("--isolated", type=bool, default=None, help="Set isolated flag")
@click.pass_context
def workspace_update(ctx, name, isolated):
    """Update workspace settings."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if isolated is not None:
            kwargs["isolated"] = isolated
        result = client.update_workspace(name, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"Workspace '{name}' updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


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


# ── Namespace Commands ───────────────────────────────────────────────────


@cli.group()
@click.pass_context
def namespace(ctx):
    """Namespace management commands."""
    pass


@namespace.command("list")
@click.pass_context
def namespace_list(ctx):
    """List all namespaces."""
    try:
        client = _get_client(ctx)
        namespaces = client.list_namespaces()
        _output(ctx, namespaces, lambda d: _print_list_names(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@namespace.command("get")
@click.argument("prefix")
@click.pass_context
def namespace_get(ctx, prefix):
    """Get namespace details."""
    try:
        client = _get_client(ctx)
        data = client.get_namespace(prefix)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@namespace.command("create")
@click.argument("prefix")
@click.argument("uri")
@click.pass_context
def namespace_create(ctx, prefix, uri):
    """Create a new namespace."""
    try:
        client = _get_client(ctx)
        result = client.create_namespace(prefix, uri)
        _output(ctx, result, lambda d: click.echo(f"Namespace '{prefix}' created with URI '{uri}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@namespace.command("update")
@click.argument("prefix")
@click.option("--uri", required=True, help="New namespace URI")
@click.pass_context
def namespace_update(ctx, prefix, uri):
    """Update namespace URI."""
    try:
        client = _get_client(ctx)
        result = client.update_namespace(prefix, uri=uri)
        _output(ctx, result, lambda d: click.echo(f"Namespace '{prefix}' updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@namespace.command("delete")
@click.argument("prefix")
@click.pass_context
def namespace_delete(ctx, prefix):
    """Delete a namespace."""
    try:
        client = _get_client(ctx)
        result = client.delete_namespace(prefix)
        _output(ctx, result, lambda d: click.echo(f"Namespace '{prefix}' deleted."))
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
@click.option(
    "--type", "store_type", type=click.Choice(["data", "coverage", "all"]), default="all", help="Store type filter"
)
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
@click.option("--type", "store_type", type=click.Choice(["data", "coverage"]), default="data", help="Store type")
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


@store.command("update-datastore")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--param", "-p", multiple=True, help="Updated param as key=value")
@click.pass_context
def store_update_datastore(ctx, name, workspace, param):
    """Update a data store."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if param:
            kwargs["connectionParameters"] = {
                "entry": [{"@key": k, "$": v} for k, v in (p.split("=", 1) for p in param)]
            }
        result = client.update_datastore(workspace, name, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"Data store '{name}' updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@store.command("update-coveragestore")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--url", default=None, help="Updated coverage URL")
@click.option("--type", "store_type", default=None, help="Updated coverage store type")
@click.option("--enabled/--disabled", default=None, help="Enable or disable the store")
@click.pass_context
def store_update_coveragestore(ctx, name, workspace, url, store_type, enabled):
    """Update a coverage store."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if url is not None:
            kwargs["url"] = url
        if store_type is not None:
            kwargs["type"] = store_type
        if enabled is not None:
            kwargs["enabled"] = enabled
        result = client.update_coveragestore(workspace, name, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"Coverage store '{name}' updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@store.command("delete")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--type", "store_type", type=click.Choice(["data", "coverage"]), default="data", help="Store type")
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
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="Path to zipped shapefile")
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
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="Path to GeoTIFF file")
@click.pass_context
def store_upload_geotiff(ctx, name, workspace, file_path):
    """Upload a GeoTIFF to create a coverage store."""
    try:
        client = _get_client(ctx)
        result = client.upload_geotiff(workspace, name, file_path)
        _output(ctx, result, lambda d: click.echo(f"GeoTIFF uploaded as store '{name}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── WMS Store Commands ───────────────────────────────────────────────────


@cli.group()
@click.pass_context
def wmsstore(ctx):
    """Cascaded WMS store management commands."""
    pass


@wmsstore.command("list")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.pass_context
def wmsstore_list(ctx, workspace):
    """List cascaded WMS stores in a workspace."""
    try:
        client = _get_client(ctx)
        stores = client.list_wmsstores(workspace)
        _output(ctx, stores, lambda d: _print_list_names(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmsstore.command("get")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.pass_context
def wmsstore_get(ctx, name, workspace):
    """Get WMS store details."""
    try:
        client = _get_client(ctx)
        data = client.get_wmsstore(workspace, name)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmsstore.command("create")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--url", "capabilities_url", required=True, help="Remote WMS capabilities URL")
@click.pass_context
def wmsstore_create(ctx, name, workspace, capabilities_url):
    """Create a cascaded WMS store."""
    try:
        client = _get_client(ctx)
        result = client.create_wmsstore(workspace, name, capabilities_url)
        _output(ctx, result, lambda d: click.echo(f"WMS store '{name}' created in '{workspace}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmsstore.command("update")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--url", "capabilities_url", default=None, help="Updated capabilities URL")
@click.option("--enabled/--disabled", default=None, help="Enable or disable the store")
@click.pass_context
def wmsstore_update(ctx, name, workspace, capabilities_url, enabled):
    """Update a cascaded WMS store."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if capabilities_url is not None:
            kwargs["capabilitiesURL"] = capabilities_url
        if enabled is not None:
            kwargs["enabled"] = enabled
        result = client.update_wmsstore(workspace, name, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"WMS store '{name}' updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmsstore.command("delete")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--recurse", is_flag=True, help="Recursively delete contents")
@click.pass_context
def wmsstore_delete(ctx, name, workspace, recurse):
    """Delete a cascaded WMS store."""
    try:
        client = _get_client(ctx)
        result = client.delete_wmsstore(workspace, name, recurse=recurse)
        _output(ctx, result, lambda d: click.echo(f"WMS store '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── WMTS Store Commands ──────────────────────────────────────────────────


@cli.group()
@click.pass_context
def wmtsstore(ctx):
    """Cascaded WMTS store management commands."""
    pass


@wmtsstore.command("list")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.pass_context
def wmtsstore_list(ctx, workspace):
    """List cascaded WMTS stores in a workspace."""
    try:
        client = _get_client(ctx)
        stores = client.list_wmtsstores(workspace)
        _output(ctx, stores, lambda d: _print_list_names(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmtsstore.command("get")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.pass_context
def wmtsstore_get(ctx, name, workspace):
    """Get WMTS store details."""
    try:
        client = _get_client(ctx)
        data = client.get_wmtsstore(workspace, name)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmtsstore.command("create")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--url", "capabilities_url", required=True, help="Remote WMTS capabilities URL")
@click.pass_context
def wmtsstore_create(ctx, name, workspace, capabilities_url):
    """Create a cascaded WMTS store."""
    try:
        client = _get_client(ctx)
        result = client.create_wmtsstore(workspace, name, capabilities_url)
        _output(ctx, result, lambda d: click.echo(f"WMTS store '{name}' created in '{workspace}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmtsstore.command("update")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--url", "capabilities_url", default=None, help="Updated capabilities URL")
@click.option("--enabled/--disabled", default=None, help="Enable or disable the store")
@click.pass_context
def wmtsstore_update(ctx, name, workspace, capabilities_url, enabled):
    """Update a cascaded WMTS store."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if capabilities_url is not None:
            kwargs["capabilitiesURL"] = capabilities_url
        if enabled is not None:
            kwargs["enabled"] = enabled
        result = client.update_wmtsstore(workspace, name, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"WMTS store '{name}' updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmtsstore.command("delete")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--recurse", is_flag=True, help="Recursively delete contents")
@click.pass_context
def wmtsstore_delete(ctx, name, workspace, recurse):
    """Delete a cascaded WMTS store."""
    try:
        client = _get_client(ctx)
        result = client.delete_wmtsstore(workspace, name, recurse=recurse)
        _output(ctx, result, lambda d: click.echo(f"WMTS store '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── WMS Layer Commands ───────────────────────────────────────────────────


@cli.group()
@click.pass_context
def wmslayer(ctx):
    """Cascaded WMS layer management commands."""
    pass


@wmslayer.command("list")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--store", "-s", default=None, help="WMS store name")
@click.pass_context
def wmslayer_list(ctx, workspace, store):
    """List cascaded WMS layers."""
    try:
        client = _get_client(ctx)
        layers = client.list_wmslayers(workspace, store=store)
        _output(ctx, layers, lambda d: _print_list_names(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmslayer.command("get")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--store", "-s", required=True, help="WMS store name")
@click.pass_context
def wmslayer_get(ctx, name, workspace, store):
    """Get WMS layer details."""
    try:
        client = _get_client(ctx)
        data = client.get_wmslayer(workspace, store, name)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmslayer.command("create")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--store", "-s", required=True, help="WMS store name")
@click.pass_context
def wmslayer_create(ctx, name, workspace, store):
    """Create a cascaded WMS layer."""
    try:
        client = _get_client(ctx)
        result = client.create_wmslayer(workspace, store, name)
        _output(ctx, result, lambda d: click.echo(f"WMS layer '{name}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmslayer.command("update")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--store", "-s", required=True, help="WMS store name")
@click.option("--enabled/--disabled", default=None, help="Enable or disable the layer")
@click.pass_context
def wmslayer_update(ctx, name, workspace, store, enabled):
    """Update a cascaded WMS layer."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if enabled is not None:
            kwargs["enabled"] = enabled
        result = client.update_wmslayer(workspace, store, name, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"WMS layer '{name}' updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmslayer.command("delete")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--store", "-s", required=True, help="WMS store name")
@click.option("--recurse", is_flag=True, help="Recursively delete")
@click.pass_context
def wmslayer_delete(ctx, name, workspace, store, recurse):
    """Delete a cascaded WMS layer."""
    try:
        client = _get_client(ctx)
        result = client.delete_wmslayer(workspace, store, name, recurse=recurse)
        _output(ctx, result, lambda d: click.echo(f"WMS layer '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── WMTS Layer Commands ──────────────────────────────────────────────────


@cli.group()
@click.pass_context
def wmtslayer(ctx):
    """Cascaded WMTS layer management commands."""
    pass


@wmtslayer.command("list")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--store", "-s", default=None, help="WMTS store name")
@click.pass_context
def wmtslayer_list(ctx, workspace, store):
    """List cascaded WMTS layers."""
    try:
        client = _get_client(ctx)
        layers = client.list_wmtslayers(workspace, store=store)
        _output(ctx, layers, lambda d: _print_list_names(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmtslayer.command("get")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--store", "-s", required=True, help="WMTS store name")
@click.pass_context
def wmtslayer_get(ctx, name, workspace, store):
    """Get WMTS layer details."""
    try:
        client = _get_client(ctx)
        data = client.get_wmtslayer(workspace, store, name)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmtslayer.command("create")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--store", "-s", required=True, help="WMTS store name")
@click.pass_context
def wmtslayer_create(ctx, name, workspace, store):
    """Create a cascaded WMTS layer."""
    try:
        client = _get_client(ctx)
        result = client.create_wmtslayer(workspace, store, name)
        _output(ctx, result, lambda d: click.echo(f"WMTS layer '{name}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmtslayer.command("update")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--store", "-s", required=True, help="WMTS store name")
@click.option("--enabled/--disabled", default=None, help="Enable or disable the layer")
@click.pass_context
def wmtslayer_update(ctx, name, workspace, store, enabled):
    """Update a cascaded WMTS layer."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if enabled is not None:
            kwargs["enabled"] = enabled
        result = client.update_wmtslayer(workspace, store, name, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"WMTS layer '{name}' updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@wmtslayer.command("delete")
@click.argument("name")
@click.option("--workspace", "-w", required=True, help="Workspace name")
@click.option("--store", "-s", required=True, help="WMTS store name")
@click.option("--recurse", is_flag=True, help="Recursively delete")
@click.pass_context
def wmtslayer_delete(ctx, name, workspace, store, recurse):
    """Delete a cascaded WMTS layer."""
    try:
        client = _get_client(ctx)
        result = client.delete_wmtslayer(workspace, store, name, recurse=recurse)
        _output(ctx, result, lambda d: click.echo(f"WMTS layer '{name}' deleted."))
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
    for lyr in layers:
        name = lyr.get("name", "") if isinstance(lyr, dict) else str(lyr)
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


@layer.command("update")
@click.argument("name")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.option("--default-style", default=None, help="Default style name")
@click.option("--enabled/--disabled", default=None, help="Enable or disable the layer")
@click.pass_context
def layer_update(ctx, name, workspace, default_style, enabled):
    """Update layer settings."""
    try:
        client = _get_client(ctx)
        workspace = workspace or ctx.obj.get("workspace")
        kwargs = {}
        if default_style is not None:
            kwargs["defaultStyle"] = {"name": default_style}
        if enabled is not None:
            kwargs["enabled"] = enabled
        result = client.update_layer(name, workspace=workspace, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"Layer '{name}' updated."))
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
@click.option("--type", "layer_type", type=click.Choice(["feature", "coverage"]), default="feature", help="Layer type")
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
@click.option("--file", "sld_file", required=True, type=click.Path(exists=True), help="Path to SLD file")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.pass_context
def style_create(ctx, name, sld_file, workspace):
    """Create a style from an SLD file."""
    try:
        client = _get_client(ctx)
        with open(sld_file) as f:
            sld_body = f.read()
        result = client.create_style(name, sld_body, workspace=workspace)
        _output(ctx, result, lambda d: click.echo(f"Style '{name}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@style.command("update")
@click.argument("name")
@click.option("--file", "sld_file", required=True, type=click.Path(exists=True), help="Path to SLD file")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.pass_context
def style_update(ctx, name, sld_file, workspace):
    """Update a style from an SLD file."""
    try:
        client = _get_client(ctx)
        with open(sld_file) as f:
            sld_body = f.read()
        result = client.update_style(name, sld_body, workspace=workspace)
        _output(ctx, result, lambda d: click.echo(f"Style '{name}' updated."))
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


@layergroup.command("update")
@click.argument("name")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.option("--layer", "-l", multiple=True, help="Layer name (repeatable, replaces all layers)")
@click.option("--title", default=None, help="Layer group title")
@click.pass_context
def layergroup_update(ctx, name, workspace, layer, title):
    """Update a layer group."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if layer:
            published = [{"@type": "layer", "name": lyr} for lyr in layer]
            kwargs["layers"] = {"published": published}
        if title is not None:
            kwargs["title"] = title
        result = client.update_layergroup(name, workspace=workspace, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"Layer group '{name}' updated."))
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


# ── Resource Commands ────────────────────────────────────────────────────


@cli.group()
@click.pass_context
def resource(ctx):
    """Data directory resource management commands."""
    pass


@resource.command("list")
@click.argument("path", default="")
@click.pass_context
def resource_list(ctx, path):
    """List data directory contents."""
    try:
        client = _get_client(ctx)
        data = client.list_resource_directory(path)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@resource.command("get")
@click.argument("path")
@click.option("--output", "-o", default=None, help="Save to file instead of stdout")
@click.pass_context
def resource_get(ctx, path, output):
    """Get a resource file from the data directory."""
    try:
        client = _get_client(ctx)
        data = client.get_resource(path)
        if output:
            if isinstance(data, bytes):
                with open(output, "wb") as f:
                    f.write(data)
            else:
                with open(output, "w") as f:
                    f.write(json_mod.dumps(data, indent=2) if isinstance(data, dict) else str(data))
            click.echo(f"Resource saved to: {output}")
        else:
            if isinstance(data, bytes):
                click.echo(f"Binary resource ({len(data)} bytes). Use --output to save.")
            else:
                _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@resource.command("put")
@click.argument("path")
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="Local file to upload")
@click.option("--content-type", default="application/octet-stream", help="Content type")
@click.pass_context
def resource_put(ctx, path, file_path, content_type):
    """Upload a file to the data directory."""
    try:
        client = _get_client(ctx)
        with open(file_path, "rb") as f:
            data = f.read()
        result = client.put_resource(path, data, content_type=content_type)
        _output(ctx, result, lambda d: click.echo(f"Resource uploaded to '{path}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@resource.command("delete")
@click.argument("path")
@click.pass_context
def resource_delete(ctx, path):
    """Delete a resource from the data directory."""
    try:
        client = _get_client(ctx)
        result = client.delete_resource(path)
        _output(ctx, result, lambda d: click.echo(f"Resource '{path}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Template Commands ────────────────────────────────────────────────────


@cli.group()
@click.pass_context
def template(ctx):
    """Freemarker template management commands."""
    pass


@template.command("list")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.option("--store", "-s", default=None, help="Store name")
@click.option("--featuretype", "-f", default=None, help="Feature type name")
@click.pass_context
def template_list(ctx, workspace, store, featuretype):
    """List Freemarker templates."""
    try:
        client = _get_client(ctx)
        data = client.list_templates(workspace=workspace, store=store, featuretype=featuretype)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@template.command("get")
@click.argument("name")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.option("--store", "-s", default=None, help="Store name")
@click.option("--featuretype", "-f", default=None, help="Feature type name")
@click.pass_context
def template_get(ctx, name, workspace, store, featuretype):
    """Get a template body."""
    try:
        client = _get_client(ctx)
        body = client.get_template(name, workspace=workspace, store=store, featuretype=featuretype)
        click.echo(body)
    except GeoServerError as e:
        _handle_error(ctx, e)


@template.command("create")
@click.argument("name")
@click.option(
    "--file", "template_file", required=True, type=click.Path(exists=True), help="Path to Freemarker template file"
)
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.option("--store", "-s", default=None, help="Store name")
@click.option("--featuretype", "-f", default=None, help="Feature type name")
@click.pass_context
def template_create(ctx, name, template_file, workspace, store, featuretype):
    """Create/upload a Freemarker template."""
    try:
        client = _get_client(ctx)
        with open(template_file) as f:
            body = f.read()
        result = client.create_template(name, body, workspace=workspace, store=store, featuretype=featuretype)
        _output(ctx, result, lambda d: click.echo(f"Template '{name}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@template.command("delete")
@click.argument("name")
@click.option("--workspace", "-w", default=None, help="Workspace name")
@click.option("--store", "-s", default=None, help="Store name")
@click.option("--featuretype", "-f", default=None, help="Feature type name")
@click.pass_context
def template_delete(ctx, name, workspace, store, featuretype):
    """Delete a Freemarker template."""
    try:
        client = _get_client(ctx)
        result = client.delete_template(name, workspace=workspace, store=store, featuretype=featuretype)
        _output(ctx, result, lambda d: click.echo(f"Template '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Security Commands ────────────────────────────────────────────────────


@cli.group()
@click.pass_context
def security(ctx):
    """Security management commands."""
    pass


# ── Security: User ──


@security.group("user")
@click.pass_context
def security_user(ctx):
    """User management commands."""
    pass


@security_user.command("list")
@click.option("--service", default="default", help="User/group service name")
@click.pass_context
def security_user_list(ctx, service):
    """List security users."""
    try:
        client = _get_client(ctx)
        data = client.list_users(service=service)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_user.command("get")
@click.argument("username")
@click.option("--service", default="default", help="User/group service name")
@click.pass_context
def security_user_get(ctx, username, service):
    """Get user details."""
    try:
        client = _get_client(ctx)
        data = client.get_user(username, service=service)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_user.command("create")
@click.argument("username")
@click.option("--password", required=True, help="User password")
@click.option("--enabled/--disabled", default=True, help="Enable or disable the user")
@click.option("--service", default="default", help="User/group service name")
@click.pass_context
def security_user_create(ctx, username, password, enabled, service):
    """Create a security user."""
    try:
        client = _get_client(ctx)
        result = client.create_user(username, password, enabled=enabled, service=service)
        _output(ctx, result, lambda d: click.echo(f"User '{username}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_user.command("update")
@click.argument("username")
@click.option("--password", default=None, help="New password")
@click.option("--enabled/--disabled", default=None, help="Enable or disable the user")
@click.option("--service", default="default", help="User/group service name")
@click.pass_context
def security_user_update(ctx, username, password, enabled, service):
    """Update a security user."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if password is not None:
            kwargs["password"] = password
        if enabled is not None:
            kwargs["enabled"] = enabled
        result = client.update_user(username, service=service, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"User '{username}' updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_user.command("delete")
@click.argument("username")
@click.option("--service", default="default", help="User/group service name")
@click.pass_context
def security_user_delete(ctx, username, service):
    """Delete a security user."""
    try:
        client = _get_client(ctx)
        result = client.delete_user(username, service=service)
        _output(ctx, result, lambda d: click.echo(f"User '{username}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Security: Group ──


@security.group("group")
@click.pass_context
def security_group(ctx):
    """User group management commands."""
    pass


@security_group.command("list")
@click.option("--service", default="default", help="User/group service name")
@click.pass_context
def security_group_list(ctx, service):
    """List user groups."""
    try:
        client = _get_client(ctx)
        data = client.list_user_groups(service=service)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_group.command("create")
@click.argument("name")
@click.option("--service", default="default", help="User/group service name")
@click.pass_context
def security_group_create(ctx, name, service):
    """Create a user group."""
    try:
        client = _get_client(ctx)
        result = client.create_user_group(name, service=service)
        _output(ctx, result, lambda d: click.echo(f"Group '{name}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_group.command("delete")
@click.argument("name")
@click.option("--service", default="default", help="User/group service name")
@click.pass_context
def security_group_delete(ctx, name, service):
    """Delete a user group."""
    try:
        client = _get_client(ctx)
        result = client.delete_user_group(name, service=service)
        _output(ctx, result, lambda d: click.echo(f"Group '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Security: Role ──


@security.group("role")
@click.pass_context
def security_role(ctx):
    """Role management commands."""
    pass


@security_role.command("list")
@click.option("--user", default=None, help="List roles for a specific user")
@click.option("--group", "group_name", default=None, help="List roles for a specific group")
@click.pass_context
def security_role_list(ctx, user, group_name):
    """List roles (optionally filtered by user or group)."""
    try:
        client = _get_client(ctx)
        if user:
            data = client.list_roles_for_user(user)
        elif group_name:
            data = client.list_roles_for_group(group_name)
        else:
            data = client.list_roles()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_role.command("create")
@click.argument("name")
@click.pass_context
def security_role_create(ctx, name):
    """Create a role."""
    try:
        client = _get_client(ctx)
        result = client.create_role(name)
        _output(ctx, result, lambda d: click.echo(f"Role '{name}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_role.command("delete")
@click.argument("name")
@click.pass_context
def security_role_delete(ctx, name):
    """Delete a role."""
    try:
        client = _get_client(ctx)
        result = client.delete_role(name)
        _output(ctx, result, lambda d: click.echo(f"Role '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_role.command("assign-user")
@click.argument("role")
@click.argument("username")
@click.pass_context
def security_role_assign_user(ctx, role, username):
    """Assign a role to a user."""
    try:
        client = _get_client(ctx)
        result = client.assign_role_to_user(role, username)
        _output(ctx, result, lambda d: click.echo(f"Role '{role}' assigned to user '{username}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_role.command("remove-user")
@click.argument("role")
@click.argument("username")
@click.pass_context
def security_role_remove_user(ctx, role, username):
    """Remove a role from a user."""
    try:
        client = _get_client(ctx)
        result = client.remove_role_from_user(role, username)
        _output(ctx, result, lambda d: click.echo(f"Role '{role}' removed from user '{username}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_role.command("assign-group")
@click.argument("role")
@click.argument("group_name")
@click.pass_context
def security_role_assign_group(ctx, role, group_name):
    """Assign a role to a group."""
    try:
        client = _get_client(ctx)
        result = client.assign_role_to_group(role, group_name)
        _output(ctx, result, lambda d: click.echo(f"Role '{role}' assigned to group '{group_name}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_role.command("remove-group")
@click.argument("role")
@click.argument("group_name")
@click.pass_context
def security_role_remove_group(ctx, role, group_name):
    """Remove a role from a group."""
    try:
        client = _get_client(ctx)
        result = client.remove_role_from_group(role, group_name)
        _output(ctx, result, lambda d: click.echo(f"Role '{role}' removed from group '{group_name}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Security: Rules ──


@security.group("rules")
@click.pass_context
def security_rules(ctx):
    """Access rules management commands."""
    pass


@security_rules.command("data")
@click.option("--set", "rules_json", default=None, help="JSON string of rules to set")
@click.pass_context
def security_rules_data(ctx, rules_json):
    """Get or set data access rules."""
    try:
        client = _get_client(ctx)
        if rules_json:
            rules = json_mod.loads(rules_json)
            result = client.set_data_access_rules(rules)
            _output(ctx, result, lambda d: click.echo("Data access rules updated."))
        else:
            data = client.get_data_access_rules()
            _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_rules.command("service")
@click.option("--set", "rules_json", default=None, help="JSON string of rules to set")
@click.pass_context
def security_rules_service(ctx, rules_json):
    """Get or set service access rules."""
    try:
        client = _get_client(ctx)
        if rules_json:
            rules = json_mod.loads(rules_json)
            result = client.set_service_access_rules(rules)
            _output(ctx, result, lambda d: click.echo("Service access rules updated."))
        else:
            data = client.get_service_access_rules()
            _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_rules.command("rest")
@click.option("--set", "rules_json", default=None, help="JSON string of rules to set")
@click.pass_context
def security_rules_rest(ctx, rules_json):
    """Get or set REST access rules."""
    try:
        client = _get_client(ctx)
        if rules_json:
            rules = json_mod.loads(rules_json)
            result = client.set_rest_access_rules(rules)
            _output(ctx, result, lambda d: click.echo("REST access rules updated."))
        else:
            data = client.get_rest_access_rules()
            _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Security: Catalog Mode ──


@security.group("catalog-mode")
@click.pass_context
def security_catalog_mode(ctx):
    """Catalog mode management commands."""
    pass


@security_catalog_mode.command("get")
@click.pass_context
def security_catalog_mode_get(ctx):
    """Get current catalog mode."""
    try:
        client = _get_client(ctx)
        data = client.get_catalog_mode()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_catalog_mode.command("set")
@click.argument("mode", type=click.Choice(["HIDE", "MIXED", "CHALLENGE"]))
@click.pass_context
def security_catalog_mode_set(ctx, mode):
    """Set catalog mode (HIDE, MIXED, or CHALLENGE)."""
    try:
        client = _get_client(ctx)
        result = client.update_catalog_mode(mode)
        _output(ctx, result, lambda d: click.echo(f"Catalog mode set to '{mode}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Security: Master Password ──


@security.group("master-password")
@click.pass_context
def security_master_password(ctx):
    """Master password management commands."""
    pass


@security_master_password.command("get")
@click.pass_context
def security_master_password_get(ctx):
    """Get master password info."""
    try:
        client = _get_client(ctx)
        data = client.get_master_password()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_master_password.command("update")
@click.option("--old-password", required=True, help="Current master password")
@click.option("--new-password", required=True, help="New master password")
@click.pass_context
def security_master_password_update(ctx, old_password, new_password):
    """Update the master password."""
    try:
        client = _get_client(ctx)
        result = client.update_master_password(old_password, new_password)
        _output(ctx, result, lambda d: click.echo("Master password updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Security: Auth Filters ──


@security.group("auth-filters")
@click.pass_context
def security_auth_filters(ctx):
    """Authentication filter management commands."""
    pass


@security_auth_filters.command("list")
@click.pass_context
def security_auth_filters_list(ctx):
    """List authentication filters."""
    try:
        client = _get_client(ctx)
        data = client.list_auth_filters()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_auth_filters.command("get")
@click.argument("name")
@click.pass_context
def security_auth_filters_get(ctx, name):
    """Get authentication filter details."""
    try:
        client = _get_client(ctx)
        data = client.get_auth_filter(name)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Security: Auth Providers ──


@security.group("auth-providers")
@click.pass_context
def security_auth_providers(ctx):
    """Authentication provider management commands."""
    pass


@security_auth_providers.command("list")
@click.pass_context
def security_auth_providers_list(ctx):
    """List authentication providers."""
    try:
        client = _get_client(ctx)
        data = client.list_auth_providers()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@security_auth_providers.command("get")
@click.argument("name")
@click.pass_context
def security_auth_providers_get(ctx, name):
    """Get authentication provider details."""
    try:
        client = _get_client(ctx)
        data = client.get_auth_provider(name)
        _output(ctx, data, lambda d: _print_detail(d))
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


@service.command("update")
@click.argument("service_name", type=click.Choice(["wms", "wfs", "wcs", "wmts"]))
@click.option("--workspace", "-w", default=None, help="Workspace-specific settings")
@click.option("--enabled/--disabled", default=None, help="Enable or disable the service")
@click.option("--title", default=None, help="Service title")
@click.option("--abstract", "abstract_text", default=None, help="Service abstract")
@click.pass_context
def service_update(ctx, service_name, workspace, enabled, title, abstract_text):
    """Update OGC service settings."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if enabled is not None:
            kwargs["enabled"] = enabled
        if title is not None:
            kwargs["title"] = title
        if abstract_text is not None:
            kwargs["abstrct"] = abstract_text
        result = client.update_service_settings(service_name, workspace=workspace, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"Service '{service_name}' settings updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── Settings Commands ────────────────────────────────────────────────────


@cli.group()
@click.pass_context
def settings(ctx):
    """Global and workspace settings commands."""
    pass


@settings.command("get")
@click.pass_context
def settings_get(ctx):
    """Get global settings."""
    try:
        client = _get_client(ctx)
        data = client.get_settings()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@settings.command("update")
@click.option("--charset", default=None, help="Character set")
@click.option("--num-decimals", type=int, default=None, help="Number of decimals")
@click.option("--verbose", type=bool, default=None, help="Verbose output")
@click.option("--param", "-p", multiple=True, help="Setting param as key=value")
@click.pass_context
def settings_update(ctx, charset, num_decimals, verbose, param):
    """Update global settings."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if charset is not None:
            kwargs["charset"] = charset
        if num_decimals is not None:
            kwargs["numDecimals"] = num_decimals
        if verbose is not None:
            kwargs["verbose"] = verbose
        for p in param:
            k, v = p.split("=", 1)
            kwargs[k] = v
        result = client.update_settings(**kwargs)
        _output(ctx, result, lambda d: click.echo("Global settings updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@settings.command("logging-get")
@click.pass_context
def settings_logging_get(ctx):
    """Get logging settings."""
    try:
        client = _get_client(ctx)
        data = client.get_logging()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@settings.command("logging-update")
@click.option("--level", default=None, help="Logging level/profile")
@click.option("--location", default=None, help="Log file location")
@click.option("--stdout/--no-stdout", default=None, help="Log to stdout")
@click.pass_context
def settings_logging_update(ctx, level, location, stdout):
    """Update logging settings."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if level is not None:
            kwargs["level"] = level
        if location is not None:
            kwargs["location"] = location
        if stdout is not None:
            kwargs["stdOutLogging"] = stdout
        result = client.update_logging(**kwargs)
        _output(ctx, result, lambda d: click.echo("Logging settings updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@settings.command("contact-get")
@click.pass_context
def settings_contact_get(ctx):
    """Get contact information."""
    try:
        client = _get_client(ctx)
        data = client.get_contact()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@settings.command("contact-update")
@click.option("--person", default=None, help="Contact person")
@click.option("--organization", default=None, help="Organization name")
@click.option("--email", default=None, help="Contact email")
@click.option("--phone", default=None, help="Contact phone")
@click.option("--address", default=None, help="Contact address")
@click.option("--city", default=None, help="City")
@click.option("--state", default=None, help="State")
@click.option("--country", default=None, help="Country")
@click.pass_context
def settings_contact_update(ctx, person, organization, email, phone, address, city, state, country):
    """Update contact information."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        if person is not None:
            kwargs["contactPerson"] = person
        if organization is not None:
            kwargs["contactOrganization"] = organization
        if email is not None:
            kwargs["contactEmail"] = email
        if phone is not None:
            kwargs["contactVoice"] = phone
        if address is not None:
            kwargs["address"] = address
        if city is not None:
            kwargs["addressCity"] = city
        if state is not None:
            kwargs["addressState"] = state
        if country is not None:
            kwargs["addressCountry"] = country
        result = client.update_contact(**kwargs)
        _output(ctx, result, lambda d: click.echo("Contact information updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@settings.command("fonts")
@click.pass_context
def settings_fonts(ctx):
    """List available fonts."""
    try:
        client = _get_client(ctx)
        data = client.list_fonts()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@settings.command("local-get")
@click.argument("workspace_name")
@click.pass_context
def settings_local_get(ctx, workspace_name):
    """Get workspace-local settings."""
    try:
        client = _get_client(ctx)
        data = client.get_local_settings(workspace_name)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@settings.command("local-create")
@click.argument("workspace_name")
@click.option("--param", "-p", multiple=True, help="Setting param as key=value")
@click.pass_context
def settings_local_create(ctx, workspace_name, param):
    """Create workspace-local settings."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        for p in param:
            k, v = p.split("=", 1)
            kwargs[k] = v
        result = client.create_local_settings(workspace_name, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"Local settings created for '{workspace_name}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@settings.command("local-update")
@click.argument("workspace_name")
@click.option("--param", "-p", multiple=True, help="Setting param as key=value")
@click.pass_context
def settings_local_update(ctx, workspace_name, param):
    """Update workspace-local settings."""
    try:
        client = _get_client(ctx)
        kwargs = {}
        for p in param:
            k, v = p.split("=", 1)
            kwargs[k] = v
        result = client.update_local_settings(workspace_name, **kwargs)
        _output(ctx, result, lambda d: click.echo(f"Local settings updated for '{workspace_name}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@settings.command("local-delete")
@click.argument("workspace_name")
@click.pass_context
def settings_local_delete(ctx, workspace_name):
    """Delete workspace-local settings."""
    try:
        client = _get_client(ctx)
        result = client.delete_local_settings(workspace_name)
        _output(ctx, result, lambda d: click.echo(f"Local settings deleted for '{workspace_name}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── GeoWebCache (GWC) Commands ───────────────────────────────────────────


@cli.group()
@click.pass_context
def gwc(ctx):
    """GeoWebCache tile caching commands."""
    pass


# ── GWC: Layer ──


@gwc.group("layer")
@click.pass_context
def gwc_layer_group(ctx):
    """GWC tile layer management commands."""
    pass


@gwc_layer_group.command("list")
@click.pass_context
def gwc_layer_list(ctx):
    """List GWC tile layers."""
    try:
        client = _get_client(ctx)
        data = client.gwc_list_layers()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc_layer_group.command("get")
@click.argument("name")
@click.pass_context
def gwc_layer_get(ctx, name):
    """Get GWC tile layer configuration."""
    try:
        client = _get_client(ctx)
        data = client.gwc_get_layer(name)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc_layer_group.command("update")
@click.argument("name")
@click.option("--config", "config_json", required=True, help="JSON string of layer config")
@click.pass_context
def gwc_layer_update(ctx, name, config_json):
    """Update GWC tile layer configuration."""
    try:
        client = _get_client(ctx)
        config = json_mod.loads(config_json)
        result = client.gwc_update_layer(name, config)
        _output(ctx, result, lambda d: click.echo(f"GWC layer '{name}' updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc_layer_group.command("delete")
@click.argument("name")
@click.pass_context
def gwc_layer_delete(ctx, name):
    """Delete a GWC tile layer."""
    try:
        client = _get_client(ctx)
        result = client.gwc_delete_layer(name)
        _output(ctx, result, lambda d: click.echo(f"GWC layer '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── GWC: Seed ──


@gwc.command("seed")
@click.argument("layer_name")
@click.option(
    "--type", "seed_type", type=click.Choice(["seed", "reseed", "truncate"]), default="seed", help="Seed operation type"
)
@click.option("--gridset", default="EPSG:4326", help="Grid set name")
@click.option("--zoom-start", type=int, default=0, help="Start zoom level")
@click.option("--zoom-stop", type=int, default=10, help="Stop zoom level")
@click.option("--format", "tile_format", default="image/png", help="Tile format")
@click.option("--threads", type=int, default=1, help="Number of threads")
@click.pass_context
def gwc_seed_cmd(ctx, layer_name, seed_type, gridset, zoom_start, zoom_stop, tile_format, threads):
    """Seed, reseed, or truncate tiles for a layer."""
    try:
        client = _get_client(ctx)
        seed_request = {
            "seedRequest": {
                "name": layer_name,
                "gridSetId": gridset,
                "zoomStart": zoom_start,
                "zoomStop": zoom_stop,
                "format": tile_format,
                "type": seed_type,
                "threadCount": threads,
            }
        }
        result = client.gwc_seed(layer_name, seed_request)
        _output(ctx, result, lambda d: click.echo(f"Seed task ({seed_type}) started for layer '{layer_name}'."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc.command("seed-status")
@click.argument("layer_name", required=False, default=None)
@click.pass_context
def gwc_seed_status_cmd(ctx, layer_name):
    """Check seed task status."""
    try:
        client = _get_client(ctx)
        data = client.gwc_seed_status(layer_name=layer_name)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc.command("terminate")
@click.argument("layer_name", required=False, default=None)
@click.pass_context
def gwc_terminate_cmd(ctx, layer_name):
    """Terminate running seed tasks."""
    try:
        client = _get_client(ctx)
        result = client.gwc_terminate_seed(layer_name=layer_name)
        _output(ctx, result, lambda d: click.echo("Seed tasks terminated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc.command("mass-truncate")
@click.option("--layer", "layer_name", default=None, help="Layer name to truncate")
@click.pass_context
def gwc_mass_truncate_cmd(ctx, layer_name):
    """Mass truncate cached tiles."""
    try:
        client = _get_client(ctx)
        result = client.gwc_mass_truncate(layer_name=layer_name)
        _output(ctx, result, lambda d: click.echo("Mass truncate completed."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── GWC: Grid Set ──


@gwc.group("gridset")
@click.pass_context
def gwc_gridset_group(ctx):
    """GWC grid set management commands."""
    pass


@gwc_gridset_group.command("list")
@click.pass_context
def gwc_gridset_list(ctx):
    """List GWC grid sets."""
    try:
        client = _get_client(ctx)
        data = client.gwc_list_gridsets()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc_gridset_group.command("get")
@click.argument("name")
@click.pass_context
def gwc_gridset_get(ctx, name):
    """Get GWC grid set details."""
    try:
        client = _get_client(ctx)
        data = client.gwc_get_gridset(name)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc_gridset_group.command("create")
@click.argument("name")
@click.option("--config", "config_json", required=True, help="JSON string of grid set config")
@click.pass_context
def gwc_gridset_create(ctx, name, config_json):
    """Create a GWC grid set."""
    try:
        client = _get_client(ctx)
        config = json_mod.loads(config_json)
        result = client.gwc_create_gridset(name, config)
        _output(ctx, result, lambda d: click.echo(f"Grid set '{name}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc_gridset_group.command("delete")
@click.argument("name")
@click.pass_context
def gwc_gridset_delete(ctx, name):
    """Delete a GWC grid set."""
    try:
        client = _get_client(ctx)
        result = client.gwc_delete_gridset(name)
        _output(ctx, result, lambda d: click.echo(f"Grid set '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── GWC: Blob Store ──


@gwc.group("blobstore")
@click.pass_context
def gwc_blobstore_group(ctx):
    """GWC blob store management commands."""
    pass


@gwc_blobstore_group.command("list")
@click.pass_context
def gwc_blobstore_list(ctx):
    """List GWC blob stores."""
    try:
        client = _get_client(ctx)
        data = client.gwc_list_blobstores()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc_blobstore_group.command("get")
@click.argument("name")
@click.pass_context
def gwc_blobstore_get(ctx, name):
    """Get GWC blob store details."""
    try:
        client = _get_client(ctx)
        data = client.gwc_get_blobstore(name)
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc_blobstore_group.command("create")
@click.argument("name")
@click.option("--config", "config_json", required=True, help="JSON string of blob store config")
@click.pass_context
def gwc_blobstore_create(ctx, name, config_json):
    """Create a GWC blob store."""
    try:
        client = _get_client(ctx)
        config = json_mod.loads(config_json)
        result = client.gwc_create_blobstore(name, config)
        _output(ctx, result, lambda d: click.echo(f"Blob store '{name}' created."))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc_blobstore_group.command("delete")
@click.argument("name")
@click.pass_context
def gwc_blobstore_delete(ctx, name):
    """Delete a GWC blob store."""
    try:
        client = _get_client(ctx)
        result = client.gwc_delete_blobstore(name)
        _output(ctx, result, lambda d: click.echo(f"Blob store '{name}' deleted."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── GWC: Disk Quota ──


@gwc.group("diskquota")
@click.pass_context
def gwc_diskquota_group(ctx):
    """GWC disk quota management commands."""
    pass


@gwc_diskquota_group.command("get")
@click.pass_context
def gwc_diskquota_get(ctx):
    """Get GWC disk quota configuration."""
    try:
        client = _get_client(ctx)
        data = client.gwc_get_diskquota()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc_diskquota_group.command("update")
@click.option("--config", "config_json", required=True, help="JSON string of disk quota config")
@click.pass_context
def gwc_diskquota_update(ctx, config_json):
    """Update GWC disk quota configuration."""
    try:
        client = _get_client(ctx)
        config = json_mod.loads(config_json)
        result = client.gwc_update_diskquota(config)
        _output(ctx, result, lambda d: click.echo("Disk quota configuration updated."))
    except GeoServerError as e:
        _handle_error(ctx, e)


# ── GWC: Global ──


@gwc.group("global")
@click.pass_context
def gwc_global_group(ctx):
    """GWC global configuration commands."""
    pass


@gwc_global_group.command("get")
@click.pass_context
def gwc_global_get(ctx):
    """Get GWC global configuration."""
    try:
        client = _get_client(ctx)
        data = client.gwc_get_global()
        _output(ctx, data, lambda d: _print_detail(d))
    except GeoServerError as e:
        _handle_error(ctx, e)


@gwc_global_group.command("update")
@click.option("--config", "config_json", required=True, help="JSON string of global config")
@click.pass_context
def gwc_global_update(ctx, config_json):
    """Update GWC global configuration."""
    try:
        client = _get_client(ctx)
        config = json_mod.loads(config_json)
        result = client.gwc_update_global(config)
        _output(ctx, result, lambda d: click.echo("GWC global configuration updated."))
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
        result = export_map(
            client, layers, output, bbox=bbox, width=width, height=height, srs=srs, format=fmt, styles=styles
        )
        _output(ctx, result, lambda d: click.echo(f"Map exported: {d['output']} ({d['file_size']:,} bytes)"))
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
        result = export_features(
            client, typenames, output, format=fmt, max_features=max_features, cql_filter=cql_filter, bbox=bbox, srs=srs
        )
        _output(ctx, result, lambda d: click.echo(f"Features exported: {d['output']} ({d['file_size']:,} bytes)"))
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
        result = export_coverage(client, coverage_id, output, format=fmt, bbox=bbox, srs=srs)
        _output(ctx, result, lambda d: click.echo(f"Coverage exported: {d['output']} ({d['file_size']:,} bytes)"))
    except GeoServerError as e:
        _handle_error(ctx, e)


@export.command("capabilities")
@click.argument("service_name", type=click.Choice(["wms", "wfs", "wcs"]))
@click.option("--output", "-o", default=None, help="Save to file instead of stdout")
@click.option("--version", "svc_version", default=None, help="Service version")
@click.pass_context
def export_capabilities_cmd(ctx, service_name, output, svc_version):
    """Get OGC capabilities document."""
    try:
        client = _get_client(ctx)
        if service_name == "wms":
            data = client.wms_getcapabilities(version=svc_version or "1.1.1")
        elif service_name == "wfs":
            data = client.wfs_getcapabilities(version=svc_version or "2.0.0")
        else:
            data = client.wcs_getcapabilities(version=svc_version or "2.0.1")
        if output:
            with open(output, "w") as f:
                f.write(data)
            click.echo(f"Capabilities saved to: {output}")
        else:
            click.echo(data)
    except GeoServerError as e:
        _handle_error(ctx, e)


@export.command("featureinfo")
@click.argument("layers")
@click.argument("output")
@click.option("--bbox", required=True, help="Bounding box: minx,miny,maxx,maxy")
@click.option("--width", default=800, help="Image width")
@click.option("--height", default=600, help="Image height")
@click.option("--x", required=True, type=int, help="Query X pixel position")
@click.option("--y", required=True, type=int, help="Query Y pixel position")
@click.option("--srs", default="EPSG:4326", help="Spatial reference system")
@click.option("--info-format", default="application/json", help="Info format")
@click.option("--feature-count", type=int, default=10, help="Max features to return")
@click.pass_context
def export_featureinfo_cmd(ctx, layers, output, bbox, width, height, x, y, srs, info_format, feature_count):
    """Get feature info via WMS GetFeatureInfo."""
    try:
        client = _get_client(ctx)
        data = client.wms_getfeatureinfo(
            layers=layers,
            bbox=bbox,
            width=width,
            height=height,
            x=x,
            y=y,
            srs=srs,
            info_format=info_format,
            feature_count=feature_count,
        )
        if isinstance(data, dict):
            with open(output, "w") as f:
                json_mod.dump(data, f, indent=2)
        else:
            with open(output, "w") as f:
                f.write(data)
        file_size = os.path.getsize(output)
        result = {"output": output, "file_size": file_size}
        _output(ctx, result, lambda d: click.echo(f"Feature info exported: {d['output']} ({d['file_size']:,} bytes)"))
    except GeoServerError as e:
        _handle_error(ctx, e)


@export.command("legendgraphic")
@click.argument("layer_name")
@click.argument("output")
@click.option("--format", "fmt", default="image/png", help="Output format")
@click.option("--width", default=20, help="Legend width")
@click.option("--height", default=20, help="Legend height")
@click.option("--style", default=None, help="Style name")
@click.pass_context
def export_legendgraphic_cmd(ctx, layer_name, output, fmt, width, height, style):
    """Get legend graphic via WMS GetLegendGraphic."""
    try:
        client = _get_client(ctx)
        data = client.wms_getlegendgraphic(layer=layer_name, format=fmt, width=width, height=height, style=style)
        with open(output, "wb") as f:
            f.write(data)
        file_size = os.path.getsize(output)
        result = {"output": output, "file_size": file_size}
        _output(ctx, result, lambda d: click.echo(f"Legend graphic exported: {d['output']} ({d['file_size']:,} bytes)"))
    except GeoServerError as e:
        _handle_error(ctx, e)


@export.command("describe-featuretype")
@click.argument("typenames")
@click.option("--output", "-o", default=None, help="Save to file instead of stdout")
@click.option("--format", "fmt", default="application/json", help="Output format")
@click.pass_context
def export_describe_featuretype_cmd(ctx, typenames, output, fmt):
    """Describe feature type via WFS DescribeFeatureType."""
    try:
        client = _get_client(ctx)
        data = client.wfs_describefeaturetype(typenames, output_format=fmt)
        if output:
            if isinstance(data, dict):
                with open(output, "w") as f:
                    json_mod.dump(data, f, indent=2)
            else:
                with open(output, "w") as f:
                    f.write(data)
            click.echo(f"DescribeFeatureType saved to: {output}")
        else:
            if isinstance(data, dict):
                _output(ctx, data, lambda d: _print_detail(d))
            else:
                click.echo(data)
    except GeoServerError as e:
        _handle_error(ctx, e)


@export.command("describe-coverage")
@click.argument("coverage_id")
@click.option("--output", "-o", default=None, help="Save to file instead of stdout")
@click.pass_context
def export_describe_coverage_cmd(ctx, coverage_id, output):
    """Describe coverage via WCS DescribeCoverage."""
    try:
        client = _get_client(ctx)
        data = client.wcs_describecoverage(coverage_id)
        if output:
            with open(output, "w") as f:
                f.write(data)
            click.echo(f"DescribeCoverage saved to: {output}")
        else:
            click.echo(data)
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
