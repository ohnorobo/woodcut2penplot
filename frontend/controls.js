/**
 * Trace Controls - dat.GUI interface for woodcut2penplot
 */

// Global state for trace data
window.traceData = null;
window.apiClient = null;

const DEFAULT_IMAGE = 'chantarelle.jpg';

// Parameters sent to the backend. The cached default response was generated
// with exactly these values, so keep them in sync with process_image.py.
const TRACE_DEFAULTS = {
  threshold: 128,
  invert: false,
  upscale: 3,
  blur: 1.0,
  despeckle: 4,
  prune: 4.0,
  max_turn: 60,
  smoothing: 1.0,
  simplify: 0.15,
  min_length: 3.0,
};

window.params = {
  ...TRACE_DEFAULTS,

  // Stroke width, applied client side
  stroke_width: 1.0,

  // Actions
  uploadImage: function() {
    document.getElementById('image-upload').click();
  },
  reprocess: function() {
    if (!window.currentImageFile) {
      showStatus('Please upload an image first', 'error');
      return;
    }

    // Check if this is the default image with default parameters
    const isDefaultImage = window.currentImageFile.name === DEFAULT_IMAGE;
    const hasDefaultParams = Object.keys(TRACE_DEFAULTS).every(
      key => params[key] === TRACE_DEFAULTS[key]
    );

    if (isDefaultImage && hasDefaultParams) {
      // Use fast cached endpoint
      loadDefaultImage();
    } else {
      // Use regular processing
      processImage(window.currentImageFile);
    }
  },
  export: function() {
    if (window.traceData) {
      exportSVG(window.traceData.result, 'centerline.svg');
    } else {
      showStatus('Please upload an image first', 'error');
    }
  }
};

/**
 * Set up dat.GUI controls
 */
function setupGUI() {
  const gui = new dat.GUI();

  // All controls at top level
  gui.add(params, 'uploadImage').name('📁 Select Image');
  gui.add(params, 'threshold', 0, 255, 1).name('Threshold');
  gui.add(params, 'invert').name('Invert');
  gui.add(params, 'blur', 0, 5, 0.1).name('Blur');
  gui.add(params, 'despeckle', 0, 50, 1).name('Despeckle');
  gui.add(params, 'upscale', 1, 6, 1).name('Upscale');
  gui.add(params, 'prune', 0, 30, 0.5).name('Prune Spurs');
  gui.add(params, 'max_turn', 0, 180, 5).name('Max Turn °');
  gui.add(params, 'smoothing', 0, 5, 0.1).name('Smoothing');
  gui.add(params, 'simplify', 0, 2, 0.05).name('Simplify');
  gui.add(params, 'min_length', 0, 50, 0.5).name('Min Length');
  gui.add(params, 'reprocess').name('🔄 Reprocess');
  gui.add(params, 'stroke_width', 0.1, 10, 0.1).name('Stroke Width')
    .onChange(() => {
      if (typeof updateStrokeWidths === 'function') {
        updateStrokeWidths();
      }
    });
  gui.add(params, 'export').name('💾 Export SVG');
}

/**
 * Initialize API client and file upload handler
 */
function initializeControls() {
  // Create API client (auto-detects environment)
  window.apiClient = new TraceAPIClient();

  // Set up file upload handler
  const fileInput = document.getElementById('image-upload');
  fileInput.addEventListener('change', handleFileUpload);

  // Check backend health
  checkBackendHealth();

  // Load default image
  loadDefaultImage();
}

/**
 * Show a thumbnail of the current source image
 */
function showPreview(file) {
  const previewContainer = document.getElementById('preview-container');
  const reader = new FileReader();
  reader.onload = function(e) {
    previewContainer.innerHTML = `<img src="${e.target.result}" alt="Preview" style="max-width: 200px; max-height: 200px;">`;
  };
  reader.readAsDataURL(file);
}

/**
 * Load and process default image on startup
 */
async function loadDefaultImage() {
  try {
    const response = await fetch(`frontend/static/${DEFAULT_IMAGE}`);
    const blob = await response.blob();
    const file = new File([blob], DEFAULT_IMAGE, { type: 'image/jpeg' });

    // Store for reprocessing
    window.currentImageFile = file;
    showPreview(file);

    // Use fast cached endpoint for the default image
    showStatus('Loading default image...', 'processing');

    try {
      const result = await window.apiClient.getCachedDefaultResponse();
      window.traceData = result;

      showStatus('Default image loaded ✓', 'success');
      setTimeout(() => showStatus('', ''), 2000);

      if (typeof renderTrace === 'function') {
        renderTrace();
      }
    } catch (error) {
      // Fallback to regular processing if cache fails
      console.warn('Cached response failed, falling back to regular processing:', error);
      await processImage(file);
    }
  } catch (error) {
    console.error('Failed to load default image:', error);
    // Silently fail - user can upload their own image
  }
}

/**
 * Check if backend is available
 */
async function checkBackendHealth() {
  try {
    await window.apiClient.healthCheck();
    // Silently succeed - only show error if backend fails
  } catch (error) {
    showStatus('Backend not available. Start server with: uvicorn backend.main:app --reload --port 8000', 'error');
  }
}

/**
 * Handle file upload
 */
async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  // Store for reprocessing
  window.currentImageFile = file;
  showPreview(file);

  // Process image
  await processImage(file);
}

/**
 * Process image through API
 */
async function processImage(file) {
  showStatus('Tracing image...', 'processing');

  try {
    const traceParams = {};
    for (const key of Object.keys(TRACE_DEFAULTS)) {
      traceParams[key] = params[key];
    }

    const result = await window.apiClient.processImage(file, traceParams);
    window.traceData = result;

    const meta = result.result.metadata;
    showStatus(`Traced ${meta.stroke_count} strokes ✓`, 'success');
    setTimeout(() => showStatus('', ''), 3000);

    if (typeof renderTrace === 'function') {
      renderTrace();
    }
  } catch (error) {
    showStatus(`Error: ${error.message}`, 'error');
    console.error('Processing error:', error);
  }
}

/**
 * Show status message
 */
let statusAnimationInterval = null;

function showStatus(message, type = '') {
  const statusDiv = document.getElementById('status-message');

  // Clear any existing animation
  if (statusAnimationInterval) {
    clearInterval(statusAnimationInterval);
    statusAnimationInterval = null;
  }

  statusDiv.className = type;

  // Animate dots for processing status
  if (type === 'processing' && message.includes('...')) {
    const baseMessage = message.replace('...', '');
    // Use non-breaking spaces ( ) to prevent HTML from trimming trailing spaces
    const dotPatterns = [ // ".  ", " . ", "  ."
      '.  ',
      ' . ',
      '  .'];
    let patternIndex = 0;

    statusDiv.textContent = baseMessage + dotPatterns[0];

    statusAnimationInterval = setInterval(() => {
      patternIndex = (patternIndex + 1) % dotPatterns.length;
      statusDiv.textContent = baseMessage + dotPatterns[patternIndex];
    }, 400);
  } else {
    statusDiv.textContent = message;
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeControls);
} else {
  initializeControls();
}
