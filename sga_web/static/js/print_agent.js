/**
 * GHS Print Agent Client Library
 * ═══════════════════════════════
 * Communicates with the local Print Agent (localhost:5555) to enable
 * direct printing from the web app, bypassing Chrome's print dialog.
 *
 * Usage:
 *   const agent = new PrintAgent();
 *   const online = await agent.checkStatus();
 *   if (online) {
 *       await agent.printImages([{ data: base64, width_mm: 200, height_mm: 150 }]);
 *   }
 */

class PrintAgent {
    constructor(port = 5555) {
        this.port = port;
        this.baseUrl = `http://127.0.0.1:${port}`;
        this.wsUrl = `ws://127.0.0.1:${port}/ws`;
        this._wsEnabled = false;
        this._wsConnecting = false;
        this.timeout = 10000; // 10s for print operations
        this._online = false;
        this._printerName = '';
        this._printerInfo = null;
        this._defaultSize = { width_mm: 200, height_mm: 150 };
        this._consecutiveFailures = 0;
        this._statusListeners = [];
    }

    connectWebSocket() {
        if (!this._wsEnabled || this._wsConnecting) {
            return;
        }

        this._wsConnecting = true;
        try {
            this.ws = new WebSocket(this.wsUrl);

            this.ws.onopen = () => {
                this._wsConnecting = false;
                this._online = true;
                this._notifyListeners();
            };

            this.ws.onclose = () => {
                this._wsConnecting = false;
                this._online = false;
                this._notifyListeners();
                setTimeout(() => this.connectWebSocket(), 5000);
            };

            this.ws.onmessage = (msg) => {
                try {
                    const data = JSON.parse(msg.data);
                    this.handleStatusUpdate(data);
                } catch (e) {
                    console.error('Error parsing WS message:', e);
                }
            };

            this.ws.onerror = (err) => {
                // Keep minimal noise in console for connection retries
                this._wsConnecting = false;
                this._online = false;
            };
        } catch (e) {
            this._wsConnecting = false;
            this._online = false;
            setTimeout(() => this.connectWebSocket(), 5000);
        }
    }

    _extractPrinterName(printer) {
        if (!printer) return '';
        if (typeof printer === 'string') return printer;
        if (typeof printer === 'object') {
            return printer.name || printer.address || '';
        }
        return '';
    }

    handleStatusUpdate(data) {
        if (data.printer) {
            this._printerInfo = data.printer;
            this._printerName = this._extractPrinterName(data.printer);
        }
        if (data.default_size) this._defaultSize = data.default_size;
        this._notifyListeners();
    }

    onStatusChange(callback) {
        this._statusListeners.push(callback);
    }

    deleteStatusListener(callback) {
        this._statusListeners = this._statusListeners.filter(l => l !== callback);
    }

    _notifyListeners() {
        this._statusListeners.forEach(cb => cb(this._online, this._printerName));
    }

    /**
     * Check if the print agent is running.
     * @returns {Promise<boolean>}
     */
    async checkStatus() {
        // Since we migrated to WebSockets, we can mostly rely on the WS connection state.
        // However, we also implement the recommended document visibility check to avoid false timeouts.
        if (document.visibilityState === 'hidden') {
            return this._online;
        }

        try {
            const controller = new AbortController();
            // INCREASED TIMEOUT: Give Windows networking enough time to clear AV checks
            const timer = setTimeout(() => controller.abort(), 3500);

            const res = await fetch(`${this.baseUrl}/status`, {
                signal: controller.signal,
                mode: 'cors',
            });
            clearTimeout(timer);

            if (res.ok) {
                const data = await res.json();
                this._online = true;
                this._consecutiveFailures = 0;
                this._printerInfo = data.printer || null;
                this._printerName = this._extractPrinterName(data.printer);
                this._defaultSize = data.default_size || this._defaultSize;

                // WS is optional; only connect when the agent explicitly advertises support.
                if (!this._wsEnabled && (data.ws_url || data.websocket === true || data.ws_enabled === true)) {
                    this._wsEnabled = true;
                    if (data.ws_url && typeof data.ws_url === 'string') {
                        this.wsUrl = data.ws_url;
                    }
                    this.connectWebSocket();
                }

                this._notifyListeners();
                return true;
            }
        } catch (e) {
            // Do not mark offline if document is hidden (Tab Throttling)
            if (document.visibilityState !== 'hidden') {
                this._consecutiveFailures++;
            }
        }

        // If WS is connected, trust WS over a single fetch failure.
        if (this._wsEnabled && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this._online = true;
            return true;
        }

        this._online = false;
        return false;
    }

    /** How many seconds to wait before next poll (backs off when offline) */
    get pollInterval() {
        if (this._online) return 30000; // 30s when online
        // Back off: 30s, 60s, 120s, max 120s
        const backoff = Math.min(30000 * Math.pow(2, this._consecutiveFailures - 1), 120000);
        return Math.max(30000, backoff);
    }

    /** @returns {boolean|null} Last known status (null = not checked yet) */
    get isOnline() {
        return this._online;
    }

    /** @returns {string} Configured printer name */
    get printerName() {
        return this._printerName;
    }

    /** @returns {object|null} Last known printer info payload from /status */
    get printerInfo() {
        return this._printerInfo;
    }

    /** @returns {{width_mm: number, height_mm: number}} */
    get defaultSize() {
        return this._defaultSize;
    }

    /**
     * Get list of available printers from the agent machine.
     * @returns {Promise<Array<{name: string, is_default: boolean}>>}
     */
    async getPrinters() {
        try {
            const res = await fetch(`${this.baseUrl}/printers`);
            if (res.ok) {
                const data = await res.json();
                return data.printers || [];
            }
        } catch (e) { }
        return [];
    }

    /**
     * Print one or more label images via the agent.
     * 
     * @param {Array<{data: string, width_mm?: number, height_mm?: number, copies?: number}>} images
     *   Array of image objects. `data` is base64-encoded image (PNG/JPG).
     * @param {string} [printer] - Override printer name (optional)
     * @returns {Promise<{success: boolean, total_printed: number, errors: string[]}>}
     */
    async printImages(images, printer = null) {
        const body = {
            images: images.map(img => ({
                data: img.data,
                width_mm: img.width_mm || this._defaultSize.width_mm,
                height_mm: img.height_mm || this._defaultSize.height_mm,
                copies: img.copies || 1,
                orientation: img.orientation || 'landscape',
            })),
        };

        if (printer) {
            body.printer = printer;
        }

        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout + (images.length * 5000));

        try {
            const res = await fetch(`${this.baseUrl}/print`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal: controller.signal,
            });
            clearTimeout(timer);

            const data = await res.json();
            return data;
        } catch (e) {
            clearTimeout(timer);
            if (e.name === 'AbortError') {
                return { success: false, total_printed: 0, errors: ['Print request timed out'] };
            }
            return { success: false, total_printed: 0, errors: [e.message] };
        }
    }

    /**
     * Print a single image (convenience method).
     * 
     * @param {string} base64Data - Base64-encoded image data
     * @param {number} [widthMm=200]
     * @param {number} [heightMm=150]
     * @param {number} [copies=1]
     * @returns {Promise<{success: boolean, total_printed: number, errors: string[]}>}
     */
    async printSingle(base64Data, widthMm, heightMm, copies = 1) {
        return this.printImages([{
            data: base64Data,
            width_mm: widthMm || this._defaultSize.width_mm,
            height_mm: heightMm || this._defaultSize.height_mm,
            copies: copies,
        }]);
    }

    /**
     * Convert an <img> element or image URL to base64.
     * 
     * @param {string|HTMLImageElement} source - Image URL or <img> element
     * @returns {Promise<string>} Base64-encoded image data (without data: prefix)
     */
    async imageToBase64(source) {
        return new Promise((resolve, reject) => {
            const img = (typeof source === 'string') ? new window.Image() : source;

            const convert = () => {
                try {
                    const canvas = document.createElement('canvas');
                    canvas.width = img.naturalWidth || img.width;
                    canvas.height = img.naturalHeight || img.height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0);
                    const dataUrl = canvas.toDataURL('image/png');
                    // Strip the data:image/png;base64, prefix
                    resolve(dataUrl.split(',')[1]);
                } catch (e) {
                    reject(e);
                }
            };

            if (typeof source === 'string') {
                img.crossOrigin = 'anonymous';
                img.onload = convert;
                img.onerror = () => reject(new Error('Failed to load image'));
                img.src = source;
            } else if (img.complete) {
                convert();
            } else {
                img.onload = convert;
                img.onerror = () => reject(new Error('Failed to load image'));
            }
        });
    }

    /**
     * Fetch an image URL as base64 via a server-side proxy to avoid CORS issues.
     * Falls back to canvas method if fetch works.
     * 
     * @param {string} url - Image URL (can be relative to the server)
     * @returns {Promise<string>} Base64-encoded image data
     */
    async fetchImageAsBase64(url) {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const blob = await response.blob();
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64 = reader.result.split(',')[1];
                    resolve(base64);
                };
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });
        } catch (e) {
            // Fallback to canvas method
            return this.imageToBase64(url);
        }
    }

    /**
     * Send a test print to verify connectivity.
     * @param {string} [printer] - Optional printer name
     * @returns {Promise<{success: boolean, message?: string, error?: string}>}
     */
    async testPrint(printer = null) {
        try {
            const body = printer ? { printer } : {};
            const res = await fetch(`${this.baseUrl}/test`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            return await res.json();
        } catch (e) {
            return { success: false, error: e.message };
        }
    }

    /**
     * Stop active printing in emergency cases
     * @returns {Promise<boolean>}
     */
    async cancelPrint() {
        try {
            const res = await fetch(`${this.baseUrl}/cancel`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            return res.ok;
        } catch (e) {
            console.error('Error al cancelar la impresión:', e);
            return false;
        }
    }

}

// Make globally available
window.PrintAgent = PrintAgent;
