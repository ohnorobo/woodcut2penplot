"""
Generate cached response for the default chantarelle.jpg image.
Run this script to create/update the cached response.

Usage: python -m backend.scripts.generate_default_cache
"""
import json
from pathlib import Path
from PIL import Image
from backend.services.process_image import process_image_to_svg

DEFAULT_IMAGE = "chantarelle.jpg"


def generate_cache():
    root = Path(__file__).parent.parent.parent
    image_path = root / "frontend" / "static" / DEFAULT_IMAGE

    if not image_path.exists():
        print(f"❌ Error: {DEFAULT_IMAGE} not found at {image_path}")
        return

    # Load the image
    pil_image = Image.open(image_path)

    print(f"Processing {DEFAULT_IMAGE} with default parameters...")

    # Process with default parameters using service layer
    result = process_image_to_svg(pil_image=pil_image)

    # Wrap result in API response format
    api_response = {
        "status": "completed",
        "result": result
    }

    # Save to frontend cache file (no backend dependency)
    cache_dir = root / "frontend" / "cache"
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / "default.json"

    with open(cache_file, "w") as f:
        json.dump(api_response, f)

    print(f"✓ Cached response saved to {cache_file}")
    print(f"  Response size: {len(json.dumps(api_response)):,} bytes")
    print(f"  Cache file size: {cache_file.stat().st_size:,} bytes")

if __name__ == "__main__":
    generate_cache()
