/**
 * Display stroke width in SVG user units (processing pixels), converted
 * from the mm value in the UI with the scale the backend reports
 * @param {Object} metadata - Result metadata with mm_per_px
 * @returns {number} stroke width in pixels
 */
function strokeWidthPx(metadata) {
  const mmPerPx = (metadata && metadata.mm_per_px) || 1;
  return window.params.stroke_width / mmPerPx;
}

/**
 * Export the traced SVG with the current stroke width and physical size
 * @param {Object} result - Result object from API with svg and metadata
 * @param {string} filename - Output filename
 */
function exportSVG(result, filename) {
  if (!result || !result.svg) {
    console.error('No trace data to export');
    return;
  }

  // Start from the original svg string to preserve Inkscape
  // namespace attributes (inkscape:groupmode, inkscape:label) that get
  // stripped when the browser DOM round-trips the SVG.
  let source = result.svg;

  const metadata = result.metadata;
  const processingDims = metadata.processing_dimensions || metadata.original_dimensions;

  // Apply current stroke width from the UI to the plotted layer only;
  // the guide layer keeps its fixed hairline width
  const widthPx = strokeWidthPx(metadata);
  const layerRegex = /(id="centerline-layer"[^>]*>)([\s\S]*?)(<\/g>)/;
  source = source.replace(layerRegex, (match, open, content, close) => {
    const updatedContent = content.replace(
      /stroke-width="[^"]*"/g,
      `stroke-width="${widthPx}"`
    );
    return open + updatedContent + close;
  });

  // Physical size in mm, as the backend sized it from Output Height
  const widthAttr = metadata.physical_dimensions_mm[0] + 'mm';
  const heightAttr = metadata.physical_dimensions_mm[1] + 'mm';
  source = source.replace(/width="[^"]*"/, `width="${widthAttr}"`);
  source = source.replace(/height="[^"]*"/, `height="${heightAttr}"`);

  // Ensure viewBox matches processing coordinate space
  const vbAttr = `0 0 ${processingDims[0]} ${processingDims[1]}`;
  source = source.replace(/viewBox="[^"]*"/, `viewBox="${vbAttr}"`);

  downloadSVG(source, filename);
}

/**
 * Helper function to download SVG content
 * @param {string} source - SVG content as string
 * @param {string} filename - Output filename
 */
function downloadSVG(source, filename) {
  const blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
