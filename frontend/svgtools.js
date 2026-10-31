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

  // Apply current stroke width from the UI
  source = source.replace(
    /stroke-width="[^"]*"/g,
    `stroke-width="${window.params.stroke_width}"`
  );

  // Update dimensions to physical units
  const metadata = result.metadata;
  const processingDims = metadata.processing_dimensions || metadata.original_dimensions;
  let widthAttr, heightAttr;
  if (metadata.physical_dimensions_mm) {
    widthAttr = metadata.physical_dimensions_mm[0] + 'mm';
    heightAttr = metadata.physical_dimensions_mm[1] + 'mm';
  } else {
    const scale = Math.min(210 / processingDims[0], 297 / processingDims[1]);
    widthAttr = Math.round(processingDims[0] * scale * 100) / 100 + 'mm';
    heightAttr = Math.round(processingDims[1] * scale * 100) / 100 + 'mm';
  }
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
