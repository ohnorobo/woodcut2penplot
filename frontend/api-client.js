/**
 * API client for communicating with the woodcut2penplot backend
 */

class TraceAPIClient {
  constructor() {
    // Auto-detect backend based on environment
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      // Running locally
      this.baseURL = 'http://localhost:8000';
    } else {
      // Deployed backend (not set up yet)
      this.baseURL = 'https://woodcut2penplot.onrender.com';
    }
  }

  /**
   * Trace an image's centerlines through the backend
   *
   * @param {File} imageFile - The image file to process
   * @param {Object} params - Trace parameters, see TRACE_DEFAULTS in controls.js
   * @returns {Promise<Object>} Response with result.svg and result.metadata
   */
  async processImage(imageFile, params = {}) {
    // Build FormData with file and parameters
    const formData = new FormData();
    formData.append('image', imageFile);
    for (const [key, value] of Object.entries(params)) {
      formData.append(key, value);
    }

    try {
      const response = await fetch(`${this.baseURL}/api/process-image`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API error:', error);
      throw error;
    }
  }

  /**
   * Get cached response for the default image (fast path)
   * Loads from local JSON file, no backend required
   *
   * @returns {Promise<Object>} Cached response with svg and metadata
   */
  async getCachedDefaultResponse() {
    try {
      const response = await fetch('frontend/cache/default.json');

      if (!response.ok) {
        throw new Error(`Failed to load cached response: HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Cached default fetch failed:', error);
      throw error;
    }
  }

  /**
   * Check backend health status
   *
   * @returns {Promise<Object>} Health status response
   */
  async healthCheck() {
    try {
      const response = await fetch(`${this.baseURL}/health`);
      return await response.json();
    } catch (error) {
      console.error('Health check failed:', error);
      throw error;
    }
  }
}

// Export for use in other modules
window.TraceAPIClient = TraceAPIClient;
