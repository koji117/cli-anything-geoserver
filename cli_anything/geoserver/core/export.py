"""Export module — download maps, features, and coverages from GeoServer."""

import os


def export_map(
    client,
    layers,
    output_path,
    bbox=None,
    width=800,
    height=600,
    srs="EPSG:4326",
    format="image/png",
    styles="",
    transparent=True,
):
    """Export a map image via WMS GetMap.

    Args:
        client: GeoServerClient instance
        layers: Comma-separated layer names
        output_path: Path to save the image
        bbox: Bounding box as "minx,miny,maxx,maxy"
        width: Image width in pixels
        height: Image height in pixels
        srs: Spatial reference system
        format: Image format (image/png, image/jpeg, image/tiff, application/pdf)
        styles: Comma-separated style names
        transparent: Whether to use transparent background

    Returns:
        dict with output path and metadata
    """
    if not bbox:
        bbox = "-180,-90,180,90"

    data = client.wms_getmap(
        layers=layers,
        bbox=bbox,
        width=width,
        height=height,
        srs=srs,
        format=format,
        styles=styles,
        transparent=transparent,
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)

    file_size = os.path.getsize(output_path)
    return {
        "output": output_path,
        "file_size": file_size,
        "layers": layers,
        "format": format,
        "width": width,
        "height": height,
        "srs": srs,
        "bbox": bbox,
    }


def export_features(
    client,
    typenames,
    output_path,
    format="application/json",
    max_features=None,
    cql_filter=None,
    bbox=None,
    srs="EPSG:4326",
):
    """Export features via WFS GetFeature.

    Args:
        client: GeoServerClient instance
        typenames: Layer name(s) to export
        output_path: Path to save the output
        format: Output format (application/json, csv, shape-zip, application/gml+xml, etc.)
        max_features: Maximum number of features
        cql_filter: CQL filter expression
        bbox: Bounding box filter
        srs: Spatial reference system

    Returns:
        dict with output path and metadata
    """
    data = client.wfs_getfeature(
        typenames=typenames,
        format=format,
        max_features=max_features,
        cql_filter=cql_filter,
        bbox=bbox,
        srs=srs,
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    if isinstance(data, dict):
        import json

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
    elif isinstance(data, bytes):
        with open(output_path, "wb") as f:
            f.write(data)
    else:
        with open(output_path, "w") as f:
            f.write(data)

    file_size = os.path.getsize(output_path)
    result = {
        "output": output_path,
        "file_size": file_size,
        "typenames": typenames,
        "format": format,
        "srs": srs,
    }
    if max_features:
        result["max_features"] = max_features
    if cql_filter:
        result["cql_filter"] = cql_filter
    return result


def export_coverage(client, coverage_id, output_path, format="image/tiff", bbox=None, srs="EPSG:4326"):
    """Export raster data via WCS GetCoverage.

    Args:
        client: GeoServerClient instance
        coverage_id: Coverage identifier
        output_path: Path to save the output
        format: Output format (image/tiff, image/png, etc.)
        bbox: Bounding box as "minx,miny,maxx,maxy"
        srs: Spatial reference system

    Returns:
        dict with output path and metadata
    """
    data = client.wcs_getcoverage(
        coverage_id=coverage_id,
        format=format,
        bbox=bbox,
        srs=srs,
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)

    file_size = os.path.getsize(output_path)
    return {
        "output": output_path,
        "file_size": file_size,
        "coverage_id": coverage_id,
        "format": format,
        "srs": srs,
    }
