"""Image processing service: centerline tracing and SVG generation."""

from PIL import Image
import os
from datetime import datetime
from typing import Dict

from backend.services.centerline import trace_centerlines, binarize
from backend.services.svg_writer import strokes_to_svg
from backend.config import DEBUG, DEBUG_DIR

# Maximum dimension for image processing (to improve performance).
# The tracer works at upscale x this resolution, so keep it moderate.
MAX_IMAGE_DIMENSION = 1600


def resize_image_if_needed(image: Image.Image, max_dimension: int = MAX_IMAGE_DIMENSION) -> Image.Image:
    """
    Resize image if either dimension exceeds max_dimension, maintaining aspect ratio.

    Args:
        image: PIL Image to potentially resize
        max_dimension: Maximum width or height in pixels

    Returns:
        Resized PIL Image (or original if already small enough)
    """
    width, height = image.size

    # Check if resize is needed
    if width <= max_dimension and height <= max_dimension:
        return image

    # Calculate new dimensions maintaining aspect ratio
    if width > height:
        new_width = max_dimension
        new_height = int(height * (max_dimension / width))
    else:
        new_height = max_dimension
        new_width = int(width * (max_dimension / height))

    # Resize using high-quality Lanczos resampling
    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    print(f"  Resized from {width}x{height} to {new_width}x{new_height} for faster processing")

    return resized


def process_image_to_svg(
    pil_image: Image.Image,
    threshold: int = 128,
    invert: bool = False,
    upscale: int = 3,
    blur: float = 0.0,
    despeckle: int = 1,
    prune: float = 2.0,
    max_turn: float = 60,
    smoothing: float = 1.0,
    simplify: float = 0.15,
    min_length: float = 1.5,
) -> Dict:
    """
    Process a PIL Image into a centerline-traced SVG.

    Args:
        pil_image: PIL Image in any mode
        threshold: Gray level 0-255, darker pixels count as ink
        invert: Trace light lines on a dark background instead
        upscale: Internal resolution multiplier
        blur: Gaussian blur radius applied before thresholding
        despeckle: Ignore specks and holes up to this area in pixels
        prune: Remove dead-end branches shorter than this many pixels
        max_turn: Largest turn in degrees the pen may make through a junction
        smoothing: Gaussian sigma applied along each stroke
        simplify: Douglas-Peucker tolerance in pixels
        min_length: Drop strokes shorter than this many pixels

    Returns:
        Dict with svg and metadata
    """
    # Store original dimensions
    original_width, original_height = pil_image.size

    # Extract DPI from image metadata
    dpi = pil_image.info.get('dpi', None)

    if dpi and dpi[0] > 0 and dpi[1] > 0:
        # Use actual DPI to calculate physical dimensions
        dpi_x, dpi_y = dpi
        physical_width_mm = round(original_width / dpi_x * 25.4, 2)
        physical_height_mm = round(original_height / dpi_y * 25.4, 2)
        print(f"Processing image: {original_width}x{original_height} @ {dpi_x}x{dpi_y} DPI ({physical_width_mm}x{physical_height_mm}mm)")
    else:
        # No DPI info: fit within A4 (210x297mm) maintaining aspect ratio
        dpi_x, dpi_y = 0, 0
        A4_WIDTH_MM, A4_HEIGHT_MM = 210, 297
        scale = min(A4_WIDTH_MM / original_width, A4_HEIGHT_MM / original_height)
        physical_width_mm = round(original_width * scale, 2)
        physical_height_mm = round(original_height * scale, 2)
        print(f"Processing image: {original_width}x{original_height}, no DPI info, fit to A4 ({physical_width_mm}x{physical_height_mm}mm)")

    # Flatten transparency onto white, then convert to grayscale
    if pil_image.mode in ('RGBA', 'LA', 'P'):
        pil_image = pil_image.convert('RGBA')
        background = Image.new('RGBA', pil_image.size, (255, 255, 255, 255))
        pil_image = Image.alpha_composite(background, pil_image)
    gray = pil_image.convert('L')

    # Resize if needed for faster processing
    gray = resize_image_if_needed(gray)
    processing_width, processing_height = gray.size

    trace_params = dict(
        threshold=threshold,
        invert=invert,
        upscale=upscale,
        blur=blur,
        despeckle=despeckle,
        prune=prune,
        max_turn=max_turn,
        smoothing=smoothing,
        simplify=simplify,
        min_length=min_length,
    )

    if DEBUG:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(DEBUG_DIR, exist_ok=True)
        print(f"Saving debug files to {DEBUG_DIR}/")
        print(f"  Trace params: {trace_params}")

        ink = binarize(gray, threshold, invert, upscale, blur, despeckle)
        bilevel = Image.fromarray((~ink * 255).astype('uint8'))
        bilevel.save(os.path.join(DEBUG_DIR, f"{timestamp}_bilevel.png"))
        print(f"  Saved bilevel image ({bilevel.size[0]}x{bilevel.size[1]})")

    strokes = trace_centerlines(gray, **trace_params)
    point_count = sum(len(stroke) for stroke in strokes)

    # Use processing dimensions for viewBox coordinates, physical dimensions for size
    svg = strokes_to_svg(
        strokes,
        width=processing_width,
        height=processing_height,
        physical_width_mm=physical_width_mm,
        physical_height_mm=physical_height_mm,
    )

    if DEBUG:
        svg_debug_path = os.path.join(DEBUG_DIR, f"{timestamp}_centerline.svg")
        with open(svg_debug_path, 'w') as f:
            f.write(svg)
        print(f"  Saved SVG: {svg_debug_path} ({len(svg)} chars)")
        print(f"Processing complete! Files saved in {DEBUG_DIR}/")

    print(f"  Traced {len(strokes)} strokes, {point_count} points")

    return {
        "svg": svg,
        "metadata": {
            "original_dimensions": [original_width, original_height],
            "processing_dimensions": [processing_width, processing_height],
            "physical_dimensions_mm": [physical_width_mm, physical_height_mm],
            "dpi": [dpi_x, dpi_y],
            "stroke_count": len(strokes),
            "point_count": point_count,
        },
    }
