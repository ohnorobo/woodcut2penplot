/**
 * Simple trace visualization without p5.js
 * Just inserts SVG directly into the DOM
 */

let currentImageWidth = 0;
let currentImageHeight = 0;

/**
 * Initialize the visualization
 */
function setup() {
  setupGUI();
}

/**
 * Render the traced SVG by inserting it into the DOM
 */
function renderTrace() {
  if (!window.traceData || !window.traceData.result) return;

  const container = document.getElementById('trace-container');
  const result = window.traceData.result;
  const metadata = result.metadata;

  // Get processing dimensions (resized) for correct coordinate space
  const processingDims = metadata.processing_dimensions || metadata.original_dimensions;
  currentImageWidth = processingDims[0];
  currentImageHeight = processingDims[1];

  // Calculate scale to fit in max 800px
  const maxSize = 800;
  const scale = Math.min(maxSize / currentImageWidth, maxSize / currentImageHeight);
  const displayWidth = currentImageWidth * scale;
  const displayHeight = currentImageHeight * scale;

  // Parse the SVG
  const parser = new DOMParser();
  const svgDoc = parser.parseFromString(result.svg, 'image/svg+xml');
  const svgElement = svgDoc.documentElement;

  // Set display dimensions with viewBox for proper scaling
  svgElement.setAttribute('width', displayWidth);
  svgElement.setAttribute('height', displayHeight);
  svgElement.setAttribute('viewBox', `0 0 ${currentImageWidth} ${currentImageHeight}`);
  svgElement.style.backgroundColor = 'white';

  // Clear container and add SVG
  container.innerHTML = '';
  container.appendChild(svgElement);

  // Apply stroke width and guide visibility from current parameters
  updateStrokeWidths();
  updateGuideVisibility();
}

/**
 * Update stroke width for the plotted layer (the guide layer keeps its width)
 */
function updateStrokeWidths() {
  const svg = document.querySelector('#trace-container svg');
  if (!svg) return;

  svg.querySelectorAll('#centerline-layer path').forEach(path => {
    path.setAttribute('stroke-width', window.params.stroke_width);
  });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setup);
} else {
  setup();
}

/**
 * Show or hide the red guide layer in the preview
 */
function updateGuideVisibility() {
  const guide = document.querySelector('#trace-container svg #guide-layer');
  if (!guide) return;

  guide.setAttribute('display', window.params.show_guide ? 'inline' : 'none');
}

// Export for use by control handlers
window.updateStrokeWidths = updateStrokeWidths;
window.updateGuideVisibility = updateGuideVisibility;
