"""Centerline tracing: turn a raster image into single-stroke polylines.

An outline tracer (potrace, Inkscape "Trace Bitmap") follows both edges of every
ink line, so a pen plotter would draw each line twice. A centerline tracer finds
the single stroke running down the middle of the line instead. This is the same
job `autotrace --centerline` does for the inkscape-centerline-trace extension,
as a pipeline of small steps that are easy to change:

    grayscale -> upscale -> blur -> threshold -> despeckle -> skeletonize
              -> build graph -> prune spurs -> join strokes -> smooth -> simplify
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.morphology import remove_small_holes, remove_small_objects, skeletonize

# 8-connected neighbourhood, as (row, col) offsets
NEIGHBOURS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
CONNECT_8 = np.ones((3, 3), dtype=int)

# Pixels back along a stroke used to measure its direction at a junction
DIRECTION_WINDOW = 12


@dataclass
class Edge:
    """A chain of skeleton pixels running between two nodes."""
    start: int
    end: int
    points: np.ndarray  # (n, 2) array of (x, y), including both node centres

    @property
    def length(self) -> float:
        return float(np.linalg.norm(np.diff(self.points, axis=0), axis=1).sum())


@dataclass
class Graph:
    """Skeleton as nodes (line ends and junctions) joined by edges."""
    nodes: Dict[int, Tuple[float, float]]  # node id -> (x, y)
    edges: List[Edge]
    loops: List[np.ndarray]  # closed rings of pixels that touch no node


def binarize(
    image: Image.Image,
    threshold: int = 128,
    invert: bool = False,
    upscale: int = 3,
    blur: float = 1.0,
    despeckle: int = 4,
) -> np.ndarray:
    """
    Convert an image to a boolean ink mask.

    Args:
        image: PIL Image in L mode
        threshold: Gray level 0-255, darker pixels count as ink
        invert: Treat light pixels as ink instead (trace white lines)
        upscale: Resample by this factor first, so thin lines survive thresholding
        blur: Gaussian blur radius in source pixels
        despeckle: Remove ink specks and fill holes up to this area in source pixels

    Returns:
        Boolean array at upscaled resolution, True where there is ink
    """
    if upscale > 1:
        size = (image.width * upscale, image.height * upscale)
        image = image.resize(size, Image.Resampling.BICUBIC)

    gray = np.asarray(image, dtype=float)
    if blur > 0:
        gray = ndimage.gaussian_filter(gray, blur * upscale)

    ink = gray > threshold if invert else gray < threshold

    if despeckle > 0:
        area = despeckle * upscale * upscale
        ink = remove_small_objects(ink, max_size=area, connectivity=2)
        ink = remove_small_holes(ink, max_size=area, connectivity=1)

    return ink


def build_graph(skeleton: np.ndarray) -> Graph:
    """
    Convert a 1px wide skeleton into a graph.

    Pixels with exactly two neighbours are the middle of a line. Everything else
    is a line end or junction, and touching junction pixels are merged into a
    single node.
    """
    neighbour_count = ndimage.convolve(skeleton.astype(int), CONNECT_8, mode='constant') - 1
    node_mask = skeleton & (neighbour_count != 2)
    labels, _ = ndimage.label(node_mask, structure=CONNECT_8)

    node_pixels = defaultdict(list)
    for row, col in zip(*np.nonzero(node_mask)):
        node_pixels[int(labels[row, col])].append((int(row), int(col)))

    nodes = {
        node_id: (
            sum(col for _, col in pixels) / len(pixels),
            sum(row for row, _ in pixels) / len(pixels),
        )
        for node_id, pixels in node_pixels.items()
    }

    line_pixels = {(int(r), int(c)) for r, c in zip(*np.nonzero(skeleton & ~node_mask))}
    node_of = {pixel: node_id for node_id, pixels in node_pixels.items() for pixel in pixels}

    def neighbours(pixel):
        row, col = pixel
        return [(row + dr, col + dc) for dr, dc in NEIGHBOURS]

    edges = []
    for start, pixels in node_pixels.items():
        for pixel in pixels:
            for first in neighbours(pixel):
                if first not in line_pixels:
                    continue

                # Walk down the line until it reaches another node
                chain = [first]
                line_pixels.discard(first)
                end = None
                while end is None:
                    step = next((p for p in neighbours(chain[-1]) if p in line_pixels), None)
                    if step is None:
                        # Prefer a different node, so that a short loop back to
                        # the start node doesn't end the walk on its first pixel
                        touching = {node_of[p] for p in neighbours(chain[-1]) if p in node_of}
                        end = next((n for n in touching if n != start), start)
                    else:
                        chain.append(step)
                        line_pixels.discard(step)

                points = np.array(
                    [nodes[start]] + [(c, r) for r, c in chain] + [nodes[end]],
                    dtype=float,
                )
                edges.append(Edge(start, end, points))

    # Whatever is left forms closed rings with no junction on them
    loops = []
    while line_pixels:
        chain = [line_pixels.pop()]
        while True:
            step = next((p for p in neighbours(chain[-1]) if p in line_pixels), None)
            if step is None:
                break
            chain.append(step)
            line_pixels.discard(step)
        loops.append(np.array([(c, r) for r, c in chain + chain[:1]], dtype=float))

    return Graph(nodes, edges, loops)


def prune_spurs(graph: Graph, max_length: float) -> None:
    """
    Remove short dead-end branches.

    Skeletonizing a line with bumpy edges leaves whiskers that aren't part of the
    drawing. Removing one can expose another, so repeat until nothing changes.
    """
    while True:
        degree = _node_degrees(graph.edges)
        keep = []
        for edge in graph.edges:
            dead_end = min(degree[edge.start], degree[edge.end]) == 1
            attached = max(degree[edge.start], degree[edge.end]) > 2
            if not (dead_end and attached and edge.length < max_length):
                keep.append(edge)

        if len(keep) == len(graph.edges):
            return
        graph.edges = keep


def _node_degrees(edges: List[Edge]) -> Dict[int, int]:
    degree = defaultdict(int)
    for edge in edges:
        degree[edge.start] += 1
        degree[edge.end] += 1
    return degree


def _outgoing_direction(edge: Edge, at_start: bool) -> np.ndarray:
    """Unit vector pointing away from the node at one end of an edge."""
    points = edge.points if at_start else edge.points[::-1]
    window = points[:DIRECTION_WINDOW]
    vector = window[-1] - window[0]
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector


def join_strokes(graph: Graph, max_turn_degrees: float = 60) -> List[np.ndarray]:
    """
    Join edges into long strokes, so the pen lifts as rarely as possible.

    At each junction the two edges that line up best are joined, then the next
    best two, as long as the pen would turn less than max_turn_degrees.

    Returns:
        List of (n, 2) polylines. Closed strokes repeat their first point.
    """
    # An end is (edge index, True for the start of the edge)
    ends_at_node = defaultdict(list)
    for index, edge in enumerate(graph.edges):
        ends_at_node[edge.start].append((index, True))
        ends_at_node[edge.end].append((index, False))

    # Dot product of two outgoing directions is -1 for a straight line through
    max_dot = -np.cos(np.radians(max_turn_degrees))

    partner = {}
    for ends in ends_at_node.values():
        if len(ends) == 2:
            partner[ends[0]] = ends[1]
            partner[ends[1]] = ends[0]
            continue

        directions = [_outgoing_direction(graph.edges[i], at_start) for i, at_start in ends]
        pairs = sorted(
            (float(directions[a] @ directions[b]), a, b)
            for a in range(len(ends))
            for b in range(a + 1, len(ends))
        )
        for dot, a, b in pairs:
            if dot > max_dot:
                break
            if ends[a] not in partner and ends[b] not in partner:
                partner[ends[a]] = ends[b]
                partner[ends[b]] = ends[a]

    strokes = []
    used = set()

    def follow(end):
        """Walk from an edge end along joined edges, returning the points."""
        parts = []
        while end is not None and end[0] not in used:
            index, at_start = end
            used.add(index)
            points = graph.edges[index].points
            parts.append(points if at_start else points[::-1])
            end = partner.get((index, not at_start))
        return np.vstack(parts)

    # Strokes with a free end first, whatever remains is a closed cycle
    for index in range(len(graph.edges)):
        for at_start in (True, False):
            if index not in used and (index, at_start) not in partner:
                strokes.append(follow((index, at_start)))
    for index in range(len(graph.edges)):
        if index not in used:
            strokes.append(follow((index, True)))

    return strokes + graph.loops


def smooth_stroke(points: np.ndarray, sigma: float) -> np.ndarray:
    """Remove pixel staircase with a gaussian along the stroke, keeping its ends in place."""
    if sigma <= 0 or len(points) < 3:
        return points

    if np.array_equal(points[0], points[-1]):
        closed = points[:-1]
        smoothed = ndimage.gaussian_filter1d(closed, sigma, axis=0, mode='wrap')
        return np.vstack([smoothed, smoothed[:1]])

    smoothed = ndimage.gaussian_filter1d(points, sigma, axis=0, mode='nearest')
    smoothed[0], smoothed[-1] = points[0], points[-1]
    return smoothed


def simplify_stroke(points: np.ndarray, tolerance: float) -> np.ndarray:
    """Ramer-Douglas-Peucker: drop points within tolerance of a straight line."""
    if tolerance <= 0 or len(points) < 3:
        return points

    keep = np.zeros(len(points), dtype=bool)
    keep[0] = keep[-1] = True

    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        if last - first < 2:
            continue

        between = points[first + 1:last]
        chord = points[last] - points[first]
        chord_length = np.linalg.norm(chord)
        offsets = between - points[first]
        if chord_length > 0:
            distances = np.abs(chord[0] * offsets[:, 1] - chord[1] * offsets[:, 0]) / chord_length
        else:
            distances = np.linalg.norm(offsets, axis=1)

        farthest = int(np.argmax(distances))
        if distances[farthest] > tolerance:
            split = first + 1 + farthest
            keep[split] = True
            stack.append((first, split))
            stack.append((split, last))

    return points[keep]


def stroke_length(points: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def trace_centerlines(
    image: Image.Image,
    threshold: int = 128,
    invert: bool = False,
    upscale: int = 3,
    blur: float = 1.0,
    despeckle: int = 4,
    prune: float = 4.0,
    max_turn: float = 60,
    smoothing: float = 1.0,
    simplify: float = 0.15,
    min_length: float = 3.0,
) -> List[np.ndarray]:
    """
    Trace the centerlines of an image.

    All lengths are in source image pixels, whatever the upscale factor.

    Args:
        image: PIL Image in L mode
        threshold: Gray level 0-255, darker pixels count as ink
        invert: Treat light pixels as ink instead (trace white lines)
        upscale: Internal resolution multiplier, higher is smoother but slower
        blur: Gaussian blur radius applied before thresholding
        despeckle: Ignore specks and holes up to this area
        prune: Remove dead-end branches shorter than this
        max_turn: Largest turn in degrees the pen may make through a junction
        smoothing: Gaussian sigma applied along each stroke
        simplify: Douglas-Peucker tolerance
        min_length: Drop finished strokes shorter than this

    Returns:
        List of (n, 2) float arrays of (x, y) in source image pixels
    """
    ink = binarize(image, threshold, invert, upscale, blur, despeckle)
    graph = build_graph(skeletonize(ink))
    prune_spurs(graph, prune * upscale)

    strokes = []
    for stroke in join_strokes(graph, max_turn):
        stroke = smooth_stroke(stroke, smoothing * upscale) / upscale
        if stroke_length(stroke) >= min_length:
            strokes.append(simplify_stroke(stroke, simplify))

    return strokes
