"""Write traced strokes out as an Inkscape-layered SVG."""

from typing import List

import numpy as np
from xml.etree import ElementTree as ET


# Register Inkscape/Sodipodi namespaces so they appear in output
ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
ET.register_namespace('sodipodi', 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd')

INKSCAPE_NS = 'http://www.inkscape.org/namespaces/inkscape'

LAYER_ID = 'centerline-layer'
LAYER_LABEL = '1 K'
STROKE_COLOR = 'rgb(0, 0, 0)'


def stroke_to_path_d(points: np.ndarray) -> str:
    """Polyline as an SVG path, closed with Z when the ends coincide."""
    coords = [f'{x:.2f},{y:.2f}' for x, y in points]
    closed = len(points) > 2 and np.array_equal(points[0], points[-1])
    if closed:
        coords = coords[:-1]
    d = 'M' + ' L'.join(coords)
    return d + ' Z' if closed else d


def strokes_to_svg(
    strokes: List[np.ndarray],
    width: int,
    height: int,
    physical_width_mm: float = None,
    physical_height_mm: float = None,
    stroke_width: float = 1.0,
) -> str:
    """
    Build an SVG with one Inkscape layer holding every stroke.

    Args:
        strokes: List of (n, 2) arrays of (x, y) in pixel coordinates
        width: Width of the coordinate space in pixels (used for viewBox)
        height: Height of the coordinate space in pixels (used for viewBox)
        physical_width_mm: Physical width in mm (used for width attribute)
        physical_height_mm: Physical height in mm (used for height attribute)
        stroke_width: Initial stroke width, the frontend overrides this

    Returns:
        SVG string with Inkscape-compatible layer structure
    """
    svg_root = ET.Element('svg')
    svg_root.set('xmlns', 'http://www.w3.org/2000/svg')

    if physical_width_mm is not None and physical_height_mm is not None:
        svg_root.set('width', f'{physical_width_mm}mm')
        svg_root.set('height', f'{physical_height_mm}mm')
    else:
        svg_root.set('width', str(width))
        svg_root.set('height', str(height))

    svg_root.set('viewBox', f'0 0 {width} {height}')

    group = ET.SubElement(svg_root, 'g')
    group.set('id', LAYER_ID)
    group.set(f'{{{INKSCAPE_NS}}}groupmode', 'layer')
    group.set(f'{{{INKSCAPE_NS}}}label', LAYER_LABEL)
    group.set('fill', 'none')
    group.set('stroke', STROKE_COLOR)
    group.set('stroke-linecap', 'round')
    group.set('stroke-linejoin', 'round')

    for stroke in strokes:
        path = ET.SubElement(group, 'path')
        path.set('d', stroke_to_path_d(stroke))
        path.set('stroke-width', str(stroke_width))

    return ET.tostring(svg_root, encoding='unicode', method='xml')
