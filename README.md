# woodcut2penplot

A web application that turns line art — woodcuts, engravings, ink drawings — into pen-plotter SVG. Upload an image and get an SVG where every line in the drawing becomes a pen stroke down its centre, instead of an outline around it; lines wider than the pen become several parallel passes that converge as the line thins, and solid dark areas become nested fans of passes.

Started from [cmyk-splitter](https://github.com/ohnorobo/cmyk-splitter), which handles the web part the same way.

## Features

- **Centerline tracing** - Skeletonizes the ink, so each drawn line is plotted once rather than outlined twice
- **Width-aware passes** - Each stroke carries its local ink width; wider than the pen means parallel, slightly overlapping passes (see `multipass.py`)
- **Tunable ink detection** - Threshold, invert, blur, despeckle and internal upscale
- **Stroke cleanup** - Prune spurs, join strokes through junctions, smooth and simplify
- **Inkscape layer output** - SVG with two layers, sized in mm from the image DPI (or fit to A4): the black layer to plot, and a fixed red hairline "guide" layer on top so the line pattern stays visible at any stroke width
- **Real-time preview** - Adjust stroke width without reprocessing
- **Easy export** - Download the SVG ready to plot

## How the trace works

`backend/services/centerline.py` is the whole algorithm and is meant to be modified:

1. grayscale → upscale → blur → threshold → despeckle (`binarize`)
2. `skimage.morphology.skeletonize` thins the ink to 1px
3. `build_graph` turns the skeleton into nodes (ends, junctions) and edges (pixel chains)
4. `prune_spurs` removes short dead-end whiskers
5. `join_strokes` pairs up edges through each junction by how straight the pen would travel
6. `smooth_stroke` tidies each polyline
7. `multipass.split_stroke` spreads strokes wider than the pen into parallel passes, using the distance transform sampled along the stroke as the local width
8. `simplify_stroke` reduces points

This is the same job `autotrace -centerline` does for the
[inkscape-centerline-trace](https://github.com/fablabnbg/inkscape-centerline-trace) extension,
written in Python/NumPy so each step can be swapped out.

## Architecture

- **Backend**: FastAPI (Python) - Runs the trace
- **Frontend**: Vanilla JavaScript + dat.GUI - Interactive visualization and controls
- **Image Processing**: Pillow + NumPy + SciPy + scikit-image

## Setup

### Requirements

- Python 3.12 (recommended) or Python 3.11
- Modern web browser

### 1. Backend Setup

```bash
cd woodcut2penplot/

# Create virtual environment with Python 3.12
python3.12 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 2. Frontend Setup

No additional setup required - the frontend is a static HTML/JS application.

## Running the Application

You'll need two terminal windows running simultaneously.

### Terminal 1: Start Backend Server

```bash
cd woodcut2penplot/
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Set `DEBUG=1` to save the thresholded bitmap and SVG to `backend/services/debug_files/`.

### Terminal 2: Start Frontend Server

```bash
cd woodcut2penplot/
python3 -m http.server 8080
```

Then open http://localhost:8080

### Regenerating the default image cache

The default image is served from a cached response so the page loads without
waiting on the backend. After changing the algorithm or its defaults, run:

```bash
python -m backend.scripts.generate_default_cache
```

## Parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| Threshold | 128 | Gray level below which a pixel is ink |
| Invert | off | Trace light lines on a dark background |
| Blur | 0 | Blur radius before thresholding; hides paper grain |
| Despeckle | 1 | Ignore specks and holes up to this area (px) |
| Upscale | 3 | Internal resolution multiplier; smoother, slower |
| Prune Spurs | 2 | Remove dead-end branches shorter than this (px) |
| Max Turn | 60° | Largest turn allowed when joining strokes through a junction |
| Smoothing | 1.0 | Smoothing along each stroke |
| Simplify | 0.15 | Point reduction tolerance (px) |
| Min Length | 1.5 | Drop strokes shorter than this (px) |
| Stroke Width Input | 3.0 | Pen width the algorithm plans for (px); wider lines get parallel passes, 0 = plain centerlines |
| Pass Overlap | 0.15 | Fraction of the pen width that neighbouring passes overlap |
| Stroke Width Display | 3.0 | Line width the SVG is drawn/exported with, no reprocess needed |
| Show Guide | on | Show the red hairline guide layer in the preview |

## License

MIT
