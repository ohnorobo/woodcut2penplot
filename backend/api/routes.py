"""API routes for centerline image tracing."""

from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from PIL import Image
import io
import time

from backend.services.process_image import process_image_to_svg

router = APIRouter()


@router.post("/process-image")
async def process_image(
    image: UploadFile = File(...),
    threshold: int = Form(128),
    invert: bool = Form(False),
    upscale: int = Form(3),
    blur: float = Form(0.0),
    despeckle: int = Form(1),
    prune: float = Form(2.0),
    max_turn: float = Form(60),
    smoothing: float = Form(1.0),
    simplify: float = Form(0.15),
    min_length: float = Form(1.5),
):
    """
    Trace the centerlines of an uploaded image into an SVG.

    Args:
        image: Uploaded image file (JPEG, PNG, GIF)
        threshold: Gray level 0-255, darker pixels count as ink (default: 128)
        invert: Trace light lines on a dark background (default: false)
        upscale: Internal resolution multiplier 1-6 (default: 3)
        blur: Blur radius in pixels applied before thresholding (default: 0)
        despeckle: Ignore specks and holes up to this area in pixels (default: 1)
        prune: Remove dead-end branches shorter than this many pixels (default: 2)
        max_turn: Largest turn in degrees allowed through a junction (default: 60)
        smoothing: Smoothing sigma along each stroke in pixels (default: 1.0)
        simplify: Point reduction tolerance in pixels (default: 0.15)
        min_length: Drop strokes shorter than this many pixels (default: 1.5)

    Returns:
        JSON response with the SVG string and metadata
    """
    start_time = time.time()
    try:
        # Validate file type
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid image format")

        if not 1 <= upscale <= 6:
            raise HTTPException(status_code=400, detail="upscale must be between 1 and 6")

        # Read uploaded image
        image_data = await image.read()
        pil_image = Image.open(io.BytesIO(image_data))

        # Process image through service layer
        result = process_image_to_svg(
            pil_image=pil_image,
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

        # Log completion
        elapsed_time = time.time() - start_time
        print(f"✓ Request completed in {elapsed_time:.2f}s (file: {image.filename})")

        return {
            "status": "completed",
            "result": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        # Log error and return failure response
        elapsed_time = time.time() - start_time
        print(f"✗ Request failed after {elapsed_time:.2f}s: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process image: {str(e)}"
        )
