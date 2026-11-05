"""Draw wide lines as several parallel pen passes.

A centerline tracer reduces every ink line to one stroke, however wide the
line was. Here each stroke carries its local width (twice the distance
transform sampled along it), and a stroke wider than the pen is laid down as
K parallel passes spread across that width. Each pass sits at a fixed
fraction of the local span, so as the line thins the passes converge on the
centerline; where fewer passes are needed the inner ones simply end, and the
two outermost always survive. Solid dark regions, whose skeleton is a tree
with large radii, come out as nested fans of parallel passes.
"""

from typing import List

import numpy as np
from scipy import ndimage

# Along-stroke filtering of the width profile, in upscaled pixels / samples.
# The median kills the 1-2 px spikes the distance transform shows at every
# junction; the gaussian makes passes converge gently rather than jitter.
WIDTH_MEDIAN_SAMPLES = 9
WIDTH_SMOOTH_SIGMA = 2.0  # multiplied by the upscale factor


def width_profile(points: np.ndarray, edt: np.ndarray, upscale: int) -> np.ndarray:
    """Local ink width at each stroke point, smoothed along the stroke."""
    radius = ndimage.map_coordinates(edt, [points[:, 1], points[:, 0]], order=1, mode='nearest')
    width = 2 * radius
    if len(width) >= WIDTH_MEDIAN_SAMPLES:
        width = ndimage.median_filter(width, size=WIDTH_MEDIAN_SAMPLES, mode='nearest')
    return ndimage.gaussian_filter1d(width, WIDTH_SMOOTH_SIGMA * upscale, mode='nearest')


def _normals(points: np.ndarray) -> np.ndarray:
    tangent = np.gradient(points, axis=0)
    tangent /= np.maximum(np.linalg.norm(tangent, axis=1, keepdims=True), 1e-9)
    return np.stack([-tangent[:, 1], tangent[:, 0]], axis=1)


def passes_needed(width: np.ndarray, pen: float, overlap: float) -> np.ndarray:
    """Pen passes needed to cover each width, with neighbouring passes overlapping."""
    spacing = pen * (1 - overlap)
    return np.where(width <= pen, 1, np.ceil((width - pen) / spacing).astype(int) + 1)


def split_stroke(points: np.ndarray, width: np.ndarray, pen: float, overlap: float) -> List[np.ndarray]:
    """
    Spread one stroke into parallel pen passes across its local width.

    Args:
        points: (n, 2) stroke polyline
        width: (n,) local ink width at each point, same units as pen
        pen: Pen line width
        overlap: Fraction of the pen width that neighbouring passes overlap

    Returns:
        List of (m, 2) polylines, one per continuous run of each pass
    """
    needed = passes_needed(width, pen, overlap)
    total = int(needed.max())
    if total == 1:
        return [points]

    # Distance between the outermost pass centres: the width minus one pen
    span = np.maximum(width - pen, 0)
    normals = _normals(points)

    # Which passes are active at each point: evenly chosen, so the outer two always are
    pattern = np.zeros((total + 1, total), dtype=bool)
    for count in range(1, total + 1):
        pattern[count, np.round(np.linspace(0, total - 1, count)).astype(int)] = True
    active = pattern[needed]

    passes = []
    for index, fraction in enumerate(np.linspace(0, 1, total)):
        line = points + normals * ((fraction - 0.5) * span)[:, None]
        # Break into the runs where this pass is active
        flags = np.concatenate([[0], active[:, index].astype(int), [0]])
        edges = np.flatnonzero(np.diff(flags))
        for start, end in zip(edges[::2], edges[1::2]):
            if end - start >= 2:
                passes.append(line[start:end])

    return passes
