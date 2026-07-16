function templateDesigner() {
        return {
            // ═══ State ═══
            templateId: 1,
            templateName: 1,
            canvasWidth: 1,
            canvasHeight: 1,
            rotation: 1,
    previewItemCode: '',
    previewProductCode: '',
    previewData: {},

    async fetchPreviewData() {
        if (!this.previewProductCode) {
            alert('Por favor ingrese un código de producto (ej. IFF-QB00122)');
            return;
        }
        
        let code = this.previewProductCode;
        
        try {
            const resp = await fetch('/api/products/' + encodeURIComponent(code));
            if (!resp.ok) {
                alert('No se encontró el producto: ' + code);
                return;
            }
            const data = await resp.json();
            const p = data.product;
            
            let hCombined = (p.h_statements || []).map((s, i) => ((p.h_codes||[])[i]||'') + ': ' + s).join(' ');
            let pCombined = (p.p_statements || []).map((s, i) => ((p.p_codes||[])[i]||'') + ': ' + s).join(' ');
            
            this.previewData = {
                product_name: p.product_name || p.name,
                signal_word: p.signal_word,
                cas_number: p.cas,
                h_statements: hCombined || 'Sin indicaciones H',
                p_statements: pCombined || 'Sin consejos P',
                internal_code_text: p.internal_code,
                internal_code_barcode: p.internal_code,
                process_barcode: p.process_barcode || p.internal_code,
                lote_value: 'PREVIEW-LOTE-1234',
                peso_bruto_value: '22.50',
                peso_neto_value: '20.00',
                peso_tara_value: '2.50',
                elab_date_value: new Date().toLocaleDateString(),
                reinsp_date_value: new Date(Date.now() + 31536000000).toLocaleDateString()
            };
        } catch (e) {
            alert('Error cargando producto: ' + e);
        }
    },

            showTestPrintModal: false,
            testProductCode: '',
            testRotation: 'default',
            testFormat: 'pdf',
            testScale: 100,
            testPrinting: false,
            testPrintMessage: '',
            testPrintError: false,
            productSearchResults: [],
            productSearchHighlight: -1,
            productSearching: false,
            // Print Agent state
            printAgentOnline: false,
            printAgentPrinter: '',
            printAgentUrl: 'http://127.0.0.1:5555',
            showDirectPrintModal: false,
            directPrintProductCode: '',
            directPrintRotation: 'default',
            directPrinting: false,
            directPrintMessage: '',
            directPrintError: false,
            directProductSearchResults: [],
            directProductSearchHighlight: -1,
            directProductSearching: false,
            // User warehouse context (for conditional features like locked rotation)
            userWarehouse: '1',
            // Preview state
            showPreviewModal: false,
            previewProductCode: '',
            previewLoading: false,
            previewImageUrl: '',
            previewMessage: '',
            previewError: false,
            previewProductSearchResults: [],
            previewProductSearchHighlight: -1,
            previewProductSearching: false,
            elements: [],
            selection: [],
            selectedElement: null,
            showGrid: true,
            zoom: 1.0,
            dirty: false,
            saveMessage: '',
            saveError: false,
            pxPerMm: 3.78,
            dragging: false,
            dragOffsetX: 0,
            dragOffsetY: 0,
            dropIndicator: { visible: false, x: 0, y: 0 },
            resizing: false,
            resizeElement: null,
            initialResize: {},
            mousePos: { x: -1, y: -1 },
            availableFields: 1,
            _uidCounter: 0,
            Math: Math,
        toolboxFields: [
            // Text
            { id: 'product_name', category: 'text', label: 'Nombre Producto', icon: '🏷️', type: 'text', field: 'product_name', defaults: { font_size: 18, font_weight: 'bold', alignment: 'center', width_mm: 80 } },
            { id: 'signal_word', category: 'text', label: 'Palabra de Señal', icon: '⚠️', type: 'text', field: 'signal_word', defaults: { font_size: 13, font_weight: 'bold', alignment: 'right', color: '#dc2626', width_mm: 40 } },
            { id: 'cas_number', category: 'text', label: 'Número CAS', icon: '🔬', type: 'text', field: 'cas_number', defaults: { font_size: 6, width_mm: 40 } },
            { id: 'h_statements', category: 'text', label: 'Indicaciones H', icon: '📋', type: 'multiline', field: 'h_statements', defaults: { font_size: 5.5, width_mm: 65 } },
            { id: 'p_statements', category: 'text', label: 'Consejos P', icon: '📋', type: 'multiline', field: 'p_statements', defaults: { font_size: 5, width_mm: 65 } },
            { id: 'elab_date_value', category: 'text', label: 'Fecha Elaboración', icon: '📅', type: 'text', field: 'elab_date_value', defaults: { font_size: 16, font_weight: 'bold', width_mm: 40 } },
            { id: 'reinsp_date_value', category: 'text', label: 'Fecha Reinspección', icon: '📅', type: 'text', field: 'reinsp_date_value', defaults: { font_size: 16, font_weight: 'bold', width_mm: 40 } },
            { id: 'lote_value', category: 'text', label: 'Valor LOTE', icon: '📦', type: 'text', field: 'lote_value', defaults: { font_size: 15, font_weight: 'bold', width_mm: 40 } },
            { id: 'peso_bruto_value', category: 'text', label: 'Peso Bruto', icon: '⚖️', type: 'text', field: 'peso_bruto_value', defaults: { font_size: 14, font_weight: 'bold', width_mm: 35 } },
            { id: 'peso_tara_value', category: 'text', label: 'Peso Tara', icon: '⚖️', type: 'text', field: 'peso_tara_value', defaults: { font_size: 14, font_weight: 'bold', width_mm: 35 } },
            { id: 'peso_neto_value', category: 'text', label: 'Peso Neto', icon: '⚖️', type: 'text', field: 'peso_neto_value', defaults: { font_size: 10, font_weight: 'bold', width_mm: 35 } },
            { id: 'internal_code_text', category: 'text', label: 'Código Interno', icon: '🔖', type: 'text', field: 'internal_code_text', defaults: { font_size: 7, width_mm: 35 } },

            // Barcodes
            { id: 'process_barcode', category: 'barcode', label: 'Barcode Proceso', icon: '▐▌', type: 'barcode', field: 'process_barcode', defaults: { bar_height_mm: 8, bar_width: 1, show_text: true, font_size: 7, width_mm: 40 } },
            { id: 'internal_code_barcode', category: 'barcode', label: 'Barcode Interno', icon: '▐▌', type: 'barcode', field: 'internal_code_barcode', defaults: { bar_height_mm: 7, bar_width: 1.25, show_text: true, font_size: 7, width_mm: 40 } },
            { id: 'batch_barcode', category: 'barcode', label: 'Barcode LOTE', icon: '▐▌', type: 'barcode', field: 'batch_barcode', defaults: { bar_height_mm: 4, bar_width: 1.25, show_text: false, font_size: 7, width_mm: 40 } },
            { id: 'net_weight_barcode', category: 'barcode', label: 'Barcode Peso Neto', icon: '▐▌', type: 'barcode', field: 'net_weight_barcode', defaults: { bar_height_mm: 4, bar_width: 0.9, show_text: true, font_size: 10, width_mm: 30 } },
            { id: 'gross_weight_barcode', category: 'barcode', label: 'Barcode Peso Bruto', icon: '▐▌', type: 'barcode', field: 'gross_weight_barcode', defaults: { bar_height_mm: 4, bar_width: 0.9, show_text: true, font_size: 10, width_mm: 30 } },

            // Static labels
            { id: 'h_header', category: 'static', label: 'Encab. Peligro', icon: '📌', type: 'static', field: 'h_header', defaults: { font_size: 7, font_weight: 'bold', custom_text: 'INDICACIONES DE PELIGRO:', width_mm: 60 } },
            { id: 'p_header', category: 'static', label: 'Encab. Prudencia', icon: '📌', type: 'static', field: 'p_header', defaults: { font_size: 7, font_weight: 'bold', custom_text: 'CONSEJOS DE PRUDENCIA:', width_mm: 60 } },
            { id: 'elab_date_label', category: 'static', label: 'Etiq. F.Elaboración', icon: '📌', type: 'static', field: 'elab_date_label', defaults: { font_size: 7, font_weight: 'bold', custom_text: 'F.ELABORACION:', width_mm: 30 } },
            { id: 'reinsp_date_label', category: 'static', label: 'Etiq. F.Reinspección', icon: '📌', type: 'static', field: 'reinsp_date_label', defaults: { font_size: 7, font_weight: 'bold', custom_text: 'F.REINSPECCION:', width_mm: 30 } },
            { id: 'lote_label', category: 'static', label: 'Etiq. LOTE', icon: '📌', type: 'static', field: 'lote_label', defaults: { font_size: 10, font_weight: 'bold', custom_text: 'LOTE:', width_mm: 20 } },
            { id: 'peso_bruto_label', category: 'static', label: 'Etiq. Peso Bruto', icon: '📌', type: 'static', field: 'peso_bruto_label', defaults: { font_size: 7, font_weight: 'bold', custom_text: 'PESO BRUTO:', width_mm: 25 } },
            { id: 'peso_tara_label', category: 'static', label: 'Etiq. Peso Tara', icon: '📌', type: 'static', field: 'peso_tara_label', defaults: { font_size: 7, font_weight: 'bold', custom_text: 'PESO TARA:', width_mm: 25 } },
            { id: 'peso_neto_label', category: 'static', label: 'Etiq. Peso Neto', icon: '📌', type: 'static', field: 'peso_neto_label', defaults: { font_size: 7, font_weight: 'bold', custom_text: 'PESO NETO:', width_mm: 25 } },
            { id: 'address_footer', category: 'static', label: 'Dirección Pie', icon: '📌', type: 'static', field: 'address_footer', defaults: { font_size: 7, alignment: 'center', custom_text: 'QUIMICA BOSS San Agustin 759 Col. El Briseño, Zapopan, Jalisco, México.', width_mm: 150 } },
            { id: 'static_text', category: 'static', label: 'Texto Libre', icon: '✏️', type: 'static', field: '_custom_', defaults: { font_size: 10, custom_text: 'Texto', width_mm: 40 } },

            // Other
            { id: 'separator_line', category: 'other', label: 'Línea Separadora', icon: '➖', type: 'line', field: 'separator_line', defaults: { width_mm: 144, line_width: 1, color: '#000000' } },
            { id: 'company_logo', category: 'other', label: 'Logo Empresa', icon: '🏢', type: 'image', field: 'company_logo', src: '/static/images/logo_vertical.2.png', defaults: { width_mm: 15, height_mm: 15 } },

            // Pictograms
            { id: 'ghs01', category: 'pictogram', label: 'GHS01 - Bomba', icon: '💣', type: 'image', field: 'ghs01', src: '/static/img/pictograms/bomba.png', defaults: { width_mm: 20, height_mm: 20 } },
            { id: 'ghs02', category: 'pictogram', label: 'GHS02 - Llama', icon: '🔥', type: 'image', field: 'ghs02', src: '/static/img/pictograms/llama.png', defaults: { width_mm: 20, height_mm: 20 } },
            { id: 'ghs03', category: 'pictogram', label: 'GHS03 - Llama Círculo', icon: '⭕', type: 'image', field: 'ghs03', src: '/static/img/pictograms/llama_circulo.png', defaults: { width_mm: 20, height_mm: 20 } },
            { id: 'ghs04', category: 'pictogram', label: 'GHS04 - Gas', icon: '💨', type: 'image', field: 'ghs04', src: '/static/img/pictograms/cilindro_gas.png', defaults: { width_mm: 20, height_mm: 20 } },
            { id: 'ghs05', category: 'pictogram', label: 'GHS05 - Corrosión', icon: '🧪', type: 'image', field: 'ghs05', src: '/static/img/pictograms/corrosion.png', defaults: { width_mm: 20, height_mm: 20 } },
            { id: 'ghs06', category: 'pictogram', label: 'GHS06 - Calavera', icon: '☠️', type: 'image', field: 'ghs06', src: '/static/img/pictograms/calavera.png', defaults: { width_mm: 20, height_mm: 20 } },
            { id: 'ghs07', category: 'pictogram', label: 'GHS07 - Exclamación', icon: '❗', type: 'image', field: 'ghs07', src: '/static/img/pictograms/exclamacion.png', defaults: { width_mm: 20, height_mm: 20 } },
            { id: 'ghs08', category: 'pictogram', label: 'GHS08 - Salud', icon: '👤', type: 'image', field: 'ghs08', src: '/static/img/pictograms/peligro_salud.png', defaults: { width_mm: 20, height_mm: 20 } },
            { id: 'ghs09', category: 'pictogram', label: 'GHS09 - Ambiente', icon: '🌳', type: 'image', field: 'ghs09', src: '/static/img/pictograms/ambiente.png', defaults: { width_mm: 20, height_mm: 20 } },
            { id: 'ghs_pictograms_locked', category: 'pictogram', label: 'Pictogramas Producto', icon: '🔒', type: 'pictogram_group_locked', field: 'ghs_pictograms_locked', defaults: { width_mm: 70, height_mm: 70, picto_square_mm: 15 } },
            { id: 'ghs_pictograms_dynamic', category: 'pictogram', label: 'Pictograma Dinámico', icon: '🔄', type: 'pictogram_group_dynamic', field: 'ghs_pictograms_dynamic', defaults: { width_mm: 60, height_mm: 60, max_pictos: 6 } },
        ],

            // ═══ Init ═══
            init() {
        
        // Load existing elements
        const raw = {{ template_data.elements | tojson | safe
    }};
    this.elements = raw.map(el => ({ ...el, _uid: this.nextUid() }));
    
    // Mouse position tracker on canvas
    this.$nextTick(() => {
        const canvas = this.$refs.canvas;
        if (canvas) {
            canvas.addEventListener('mousemove', (e) => {
                const rect = canvas.getBoundingClientRect();
                this.mousePos.x = (e.clientX - rect.left) / (this.pxPerMm * this.zoom);
                this.mousePos.y = (e.clientY - rect.top) / (this.pxPerMm * this.zoom);
            });
            canvas.addEventListener('mouseleave', () => {
                this.mousePos = { x: -1, y: -1 };
            });
        }
    });

    // Auto-calculate initial zoom
    this.$nextTick(() => this.autoZoom());

    // Check Print Agent availability
    this.checkPrintAgent();
        },

    nextUid() { return ++this._uidCounter; },

    autoZoom() {
        // Simple zoom
        this.zoom = 1.6;
    },

    // ═══ Canvas rendering ═══
    canvasStyle() {
        const w = this.canvasWidth * this.pxPerMm * this.zoom;
        const h = this.canvasHeight * this.pxPerMm * this.zoom;
        let bg = '';
        if (this.showGrid) {
            const gridSize = 5 * this.pxPerMm * this.zoom; // 5mm grid
            bg = `background-size: ${gridSize}px ${gridSize}px;`;
        }
        return `width: ${w}px; height: ${h}px; ${bg}`;
    },

    updateCanvasSize() {
        this.markDirty();
        this.$nextTick(() => this.autoZoom());
    },

    syncRulers(e) {
        const target = e.target;
        if (this.$refs.rulerHWrapper) {
            this.$refs.rulerHWrapper.scrollLeft = target.scrollLeft;
        }
        if (this.$refs.rulerVWrapper) {
            this.$refs.rulerVWrapper.scrollTop = target.scrollTop;
        }
    },

    elementStyle(el) {
        const x = el.x_mm * this.pxPerMm * this.zoom;
        const y = el.y_mm * this.pxPerMm * this.zoom;
        let style = `left: ${x}px; top: ${y}px;`;
        if (el.type === 'pictogram_group_locked' || el.type === 'pictogram_group_dynamic') {
            // Use element's own width/height (editable in properties panel)
            const defW = el.type === 'pictogram_group_dynamic' ? 60 : 70;
            const defH = el.type === 'pictogram_group_dynamic' ? 60 : 70;
            const w = (el.width_mm || defW) * this.pxPerMm * this.zoom;
            const h = (el.height_mm || defH) * this.pxPerMm * this.zoom;
            style += ` width: ${w}px; height: ${h}px;`;
            return style;
        }
        if (el.width_mm) {
            style += ` width: ${el.width_mm * this.pxPerMm * this.zoom}px;`;
        }
        if (el.height_mm && (el.type === 'image' || el.type === 'pictogram_group')) {
            style += ` height: ${el.height_mm * this.pxPerMm * this.zoom}px;`;
        }
        if (el.height_mm && el.type === 'multiline') {
            style += ` height: ${el.height_mm * this.pxPerMm * this.zoom}px; overflow: hidden; border: 1px dashed rgba(59,130,246,0.3); border-radius: 2px;`;
        }
        if (el.height_mm && (el.type === 'text' || el.type === 'static')) {
            style += ` height: ${el.height_mm * this.pxPerMm * this.zoom}px; overflow: hidden; border: 1px dashed rgba(16,185,129,0.3); border-radius: 2px;`;
        }
        return style;
    },

    elementTextStyle(el) {
        const size = Math.max(8, (el.font_size || 10) * this.zoom);
        let style = `font-size: ${size}px;`;
        if (el.font_weight === 'bold') style += ' font-weight: bold;';
        if (el.alignment) style += ` text-align: ${el.alignment};`;
        if (el.color) style += ` color: ${el.color};`;
        style += ' display: block; width: 100%; overflow: hidden; text-overflow: ellipsis;';
        if (el.type === 'text' || el.type === 'static' || el.type === 'barcode') {
            style += ' white-space: nowrap;';
        }
        return style;
    },

    elementDisplayText(el) {
        if (this.previewData && this.previewData[el.field]) return this.previewData[el.field];
        if (el.custom_text) return el.custom_text;
        const fieldInfo = this.availableFields[el.field];
        if (fieldInfo) {
            if (fieldInfo.default_value) return fieldInfo.default_value;
            return `{${fieldInfo.label}}`;
        }
        return el.field || 'Elemento';
    },

    // ═══ Toolbox drag → Canvas ═══
    onToolDragStart(e, field) {
        e.dataTransfer.setData('application/json', JSON.stringify(field));
        e.dataTransfer.effectAllowed = 'copy';
    },
    onToolDragEnd(e) {
        this.dropIndicator.visible = false;
    },
    onCanvasDragOver(e) {
        e.dataTransfer.dropEffect = 'copy';
        const rect = this.$refs.canvas.getBoundingClientRect();
        this.dropIndicator.visible = true;
        this.dropIndicator.x = e.clientX - rect.left;
        this.dropIndicator.y = e.clientY - rect.top;
    },
    onCanvasDrop(e) {
        this.dropIndicator.visible = false;
        let data;
        try { data = JSON.parse(e.dataTransfer.getData('application/json')); } catch { return; }

        const rect = this.$refs.canvas.getBoundingClientRect();
        const x_mm = (e.clientX - rect.left) / (this.pxPerMm * this.zoom);
        const y_mm = (e.clientY - rect.top) / (this.pxPerMm * this.zoom);

        const newEl = {
            _uid: this.nextUid(),
            type: data.type,
            field: data.field,
            x_mm: Math.round(x_mm * 2) / 2,  // snap to 0.5mm
            y_mm: Math.round(y_mm * 2) / 2,
            font_size: 10,
            font_weight: 'normal',
            alignment: 'left',
            color: '#000000',
            src: data.src || '', // Include source for images
            ...data.defaults
        };

        if (newEl.type === 'pictogram_group_locked') {
            newEl.width_mm = newEl.width_mm || 70;
            newEl.height_mm = newEl.height_mm || 70;
            newEl.picto_square_mm = newEl.picto_square_mm || 15;
        }
        if (newEl.type === 'pictogram_group_dynamic') {
            newEl.width_mm = newEl.width_mm || 60;
            newEl.height_mm = newEl.height_mm || 60;
            newEl.max_pictos = newEl.max_pictos || 4;
        }

        this.elements.push(newEl);
        this.selectedElement = this.elements.length - 1;
        this.markDirty();
    },

    // ═══ Element dragging on canvas ═══
    onCanvasMouseDown(e) {
        // Clicked on empty canvas area
        if (e.target === this.$refs.canvas) {
            this.selectedElement = null;
            this.selection = [];
        }
    },

    startResize(e, idx) {
        this.resizing = true;
        this.resizeElement = idx;
        const el = this.elements[idx];

        // Store initial state
        this.initialResize = {
            w: el.width_mm,
            h: el.height_mm,
            mouseX: e.clientX,
            mouseY: e.clientY
        };

        const onResizeMove = (me) => {
            if (!this.resizing) return;

            const dx = (me.clientX - this.initialResize.mouseX) / (this.pxPerMm * this.zoom);
            const dy = (me.clientY - this.initialResize.mouseY) / (this.pxPerMm * this.zoom);

            let newW = this.initialResize.w + dx;
            let newH = this.initialResize.h + dy;

            // Minimum size constraint (5mm)
            newW = Math.max(5, newW);
            newH = Math.max(5, newH);

            const el = this.elements[this.resizeElement];
            if (el) {
                el.width_mm = parseFloat(newW.toFixed(1));
                el.height_mm = parseFloat(newH.toFixed(1));
            }
            this.markDirty();
        };

        const onResizeUp = () => {
            this.resizing = false;
            this.resizeElement = null;
            document.removeEventListener('mousemove', onResizeMove);
            document.removeEventListener('mouseup', onResizeUp);
        };

        document.addEventListener('mousemove', onResizeMove);
        document.addEventListener('mouseup', onResizeUp);
    },

    startDrag(e, idx) {
        // Selection Logic
        if (e.shiftKey || e.ctrlKey) {
            const sIdx = this.selection.indexOf(idx);
            if (sIdx > -1) {
                this.selection.splice(sIdx, 1);
                if (this.selectedElement === idx) {
                    this.selectedElement = this.selection.length > 0 ? this.selection[this.selection.length - 1] : null;
                }
                return;
            } else {
                this.selection.push(idx);
                this.selectedElement = idx;
            }
        } else {
            if (!this.selection.includes(idx)) {
                this.selection = [idx];
                this.selectedElement = idx;
            } else {
                this.selectedElement = idx;
            }
        }

        this.dragging = true;
        const rect = this.$refs.canvas.getBoundingClientRect();

        // Store initial positions
        const initialPositions = {};
        this.selection.forEach(sIdx => {
            const el = this.elements[sIdx];
            if (el) initialPositions[sIdx] = { x: el.x_mm, y: el.y_mm };
        });

        const mouseStartX = (e.clientX - rect.left) / (this.pxPerMm * this.zoom);
        const mouseStartY = (e.clientY - rect.top) / (this.pxPerMm * this.zoom);

        const onMove = (me) => {
            if (!this.dragging) return;
            const r = this.$refs.canvas.getBoundingClientRect();
            const currentMouseX = (me.clientX - r.left) / (this.pxPerMm * this.zoom);
            const currentMouseY = (me.clientY - r.top) / (this.pxPerMm * this.zoom);

            const deltaX = currentMouseX - mouseStartX;
            const deltaY = currentMouseY - mouseStartY;

            this.selection.forEach(sIdx => {
                const initPos = initialPositions[sIdx];
                if (!initPos) return;

                let newX = initPos.x + deltaX;
                let newY = initPos.y + deltaY;

                // Snap
                newX = Math.round(newX * 2) / 2;
                newY = Math.round(newY * 2) / 2;

                const el = this.elements[sIdx];
                newX = Math.max(0, Math.min(newX, this.canvasWidth - (el.width_mm || 0)));
                newY = Math.max(0, Math.min(newY, this.canvasHeight - (el.height_mm || 0)));

                el.x_mm = newX;
                el.y_mm = newY;
            });
            this.markDirty();
        };

        const onUp = () => {
            this.dragging = false;
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
        };

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    },

    // ═══ Keyboard shortcuts ═══
    handleKeydown(e) {
        if (this.selectedElement === null) return;
        const el = this.elements[this.selectedElement];
        if (!el) return;

        // Delete / Backspace (only if not focused on input)
        if ((e.key === 'Delete' || e.key === 'Backspace') && !['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) {
            e.preventDefault();
            this.deleteElement(this.selectedElement);
            return;
        }

        // Arrow keys for fine positioning
        const step = e.shiftKey ? 5 : 0.5;
        if (e.key === 'ArrowLeft') { e.preventDefault(); el.x_mm = Math.max(0, el.x_mm - step); this.markDirty(); }
        if (e.key === 'ArrowRight') { e.preventDefault(); el.x_mm = Math.min(this.canvasWidth, el.x_mm + step); this.markDirty(); }
        if (e.key === 'ArrowUp') { e.preventDefault(); el.y_mm = Math.max(0, el.y_mm - step); this.markDirty(); }
        if (e.key === 'ArrowDown') { e.preventDefault(); el.y_mm = Math.min(this.canvasHeight, el.y_mm + step); this.markDirty(); }
    },

    editElementText(idx) {
        const el = this.elements[idx];
        if (el.type === 'static' || el.field === '_custom_') {
            const newText = prompt('Nuevo texto:', el.custom_text || '');
            if (newText !== null) {
                el.custom_text = newText;
                this.markDirty();
            }
        }
    },

    deleteElement(idx) {
        this.elements.splice(idx, 1);
        this.selectedElement = null;
        this.markDirty();
    },

    markDirty() { this.dirty = true; },

    // ═══ Save ═══
    async openTestPrintModal() {
        this.showTestPrintModal = true;
        this.testProductCode = '';
        this.testPrintMessage = '';
        this.testFormat = 'pdf';
        this.testRotation = 'default';
        this.testScale = 100;
        this.productSearchResults = [];
        this.productSearchHighlight = -1;
    },

    async searchProducts() {
        const q = this.testProductCode.trim();
        if (q.length < 2) {
            this.productSearchResults = [];
            return;
        }
        this.productSearching = true;
        try {
            const resp = await fetch('/products/search?q=' + encodeURIComponent(q) + '&limit=8');
            const data = await resp.json();
            this.productSearchResults = data.products || [];
            this.productSearchHighlight = this.productSearchResults.length > 0 ? 0 : -1;
        } catch (e) {
            console.error('Product search failed:', e);
            this.productSearchResults = [];
        } finally {
            this.productSearching = false;
        }
    },

    selectProduct(prod) {
        this.testProductCode = prod.code;
        this.productSearchResults = [];
    },

    async runTestPrint() {
        if (!this.testProductCode) {
            this.testPrintMessage = 'Ingresa un código de producto';
            this.testPrintError = true;
            return;
        }

        this.testPrinting = true;
        if (this.testFormat.startsWith('image')) {
             this.testPrintMessage = 'Generando Imagen (' + this.testScale + '%)...';
        } else {
             this.testPrintMessage = 'Generando PDF...';
        }
        this.testPrintError = false;

        try {
            const payload = {
                product_id: this.testProductCode,
                output_format: this.testFormat,
                rotation_override: this.testRotation,
                scale_percent: this.testScale,
                template_data: {
                    id: this.templateId,
                    name: this.templateName,
                    width_mm: this.canvasWidth,
                    height_mm: this.canvasHeight,
                    rotation: this.rotation,
                    elements: this.elements
                }
            };

            const response = await fetch('/templates/' + (this.templateId || 'new') + '/test_print', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (data.success) {
                this.testPrintMessage = 'Archivo generado. Abriendo diálogo de impresión...';
                // Open in a new window and trigger print dialog
                const printWin = window.open(data.pdf_url, '_blank');
                if (printWin && data.format !== 'PDF') {
                    // For images, wait for load then trigger print
                    printWin.addEventListener('load', () => {
                        setTimeout(() => printWin.print(), 500);
                    });
                }
                this.showTestPrintModal = false;
            } else {
                this.testPrintMessage = 'Error: ' + (data.error || 'Desconocido');
                this.testPrintError = true;
            }
        } catch (e) {
            this.testPrintMessage = 'Error de conexión';
            this.testPrintError = true;
            console.error(e);
        } finally {
            this.testPrinting = false;
        }
    },
    // ═══ Print Agent Methods ═══
    async checkPrintAgent() {
        try {
            const controller = new AbortController();
            setTimeout(() => controller.abort(), 2000);
            const res = await fetch(this.printAgentUrl + '/status', { signal: controller.signal });
            if (res.ok) {
                const data = await res.json();
                this.printAgentOnline = true;
                this.printAgentPrinter = data.printer || 'Unknown';
            }
        } catch (e) {
            this.printAgentOnline = false;
        }
    },

    // ══════ Preview Modal Methods ══════
    openPreviewModal() {
        this.previewProductCode = this.testProductCode || '';
        this.previewMessage = '';
        this.previewError = false;
        this.previewImageUrl = '';
        this.previewProductSearchResults = [];
        this.previewProductSearchHighlight = -1;
        this.showPreviewModal = true;
    },

    async searchPreviewProducts() {
        if (this.previewProductCode.length < 2) {
            this.previewProductSearchResults = [];
            return;
        }
        this.previewProductSearching = true;
        try {
            const res = await fetch(`/products/search?q=${encodeURIComponent(this.previewProductCode)}`);
            if (res.ok) {
                const data = await res.json();
                this.previewProductSearchResults = data.products || [];
                this.previewProductSearchHighlight = this.previewProductSearchResults.length > 0 ? 0 : -1;
            }
        } catch (e) {
            console.error('Preview product search error:', e);
        } finally {
            this.previewProductSearching = false;
        }
    },

    selectPreviewProduct(prod) {
        this.previewProductCode = prod.code;
        this.previewProductSearchResults = [];
    },

    async loadPreviewImage() {
        if (!this.previewProductCode) return;
        this.previewLoading = true;
        this.previewMessage = '';
        this.previewError = false;
        this.previewImageUrl = '';

        try {
            const templateId = new URLSearchParams(window.location.search).get('id') || window.location.pathname.split('/designer/')[1];
            if (!templateId) {
                this.previewMessage = 'Guarda la plantilla primero antes de previsualizar.';
                this.previewError = true;
                this.previewLoading = false;
                return;
            }

            const res = await fetch(`/templates/${templateId}/test_print`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    product_code: this.previewProductCode,
                    output_format: 'image'
                })
            });

            const data = await res.json();
            if (data.success && data.pdf_url) {
                this.previewImageUrl = data.pdf_url + '?t=' + Date.now();
                this.previewMessage = '';
            } else {
                this.previewMessage = data.error || 'Error al generar la vista previa';
                this.previewError = true;
            }
        } catch (e) {
            this.previewMessage = 'Error de conexión: ' + e.message;
            this.previewError = true;
        } finally {
            this.previewLoading = false;
        }
    },

    openDirectPrintModal() {
        if (!this.printAgentOnline) {
            alert('Print Agent no disponible.\n\nInicia start_agent.bat en la PC del almac\u00e9n.');
            return;
        }
        this.directPrintProductCode = this.testProductCode || '';
        this.directPrintMessage = '';
        this.directPrintError = false;
        // Almacen2 (warehouse 02): force rotation to 90° for thermal printing
        if (this.userWarehouse === '02') {
            this.directPrintRotation = '90';
        }
        this.showDirectPrintModal = true;
    },

    async searchDirectProducts() {
        if (this.directPrintProductCode.length < 2) {
            this.directProductSearchResults = [];
            return;
        }
        this.directProductSearching = true;
        try {
            const res = await fetch('/products/search?q=' + encodeURIComponent(this.directPrintProductCode) + '&limit=8');
            const data = await res.json();
            this.directProductSearchResults = data.products || [];
        } catch (e) {
            this.directProductSearchResults = [];
        } finally {
            this.directProductSearching = false;
        }
    },

    selectDirectProduct(prod) {
        this.directPrintProductCode = prod.code;
        this.directProductSearchResults = [];
    },

    async runDirectPrint() {
        if (!this.directPrintProductCode) {
            this.directPrintMessage = 'Ingresa un c\u00f3digo de producto';
            this.directPrintError = true;
            return;
        }

        this.directPrinting = true;
        this.directPrintMessage = 'Generando imagen...';
        this.directPrintError = false;

        try {
            // Step 1: Generate image via server
            const payload = {
                product_id: this.directPrintProductCode,
                output_format: 'image',
                rotation_override: this.directPrintRotation,
                scale_percent: 100,
                render_dpi: 300,
                template_data: {
                    id: this.templateId,
                    name: this.templateName,
                    width_mm: this.canvasWidth,
                    height_mm: this.canvasHeight,
                    rotation: this.rotation,
                    elements: this.elements
                }
            };

            const genRes = await fetch('/templates/' + (this.templateId || 'new') + '/test_print', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const genData = await genRes.json();
            if (!genData.success) {
                this.directPrintMessage = 'Error: ' + (genData.error || 'Fallo al generar');
                this.directPrintError = true;
                return;
            }

            // Step 2: Fetch the generated image and convert to base64
            this.directPrintMessage = 'Enviando a impresora ' + this.printAgentPrinter + '...';

            const imgRes = await fetch(genData.pdf_url);
            const imgBlob = await imgRes.blob();
            const base64 = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result.split(',')[1]);
                reader.onerror = reject;
                reader.readAsDataURL(imgBlob);
            });

            // Step 3: Send to Print Agent
            // Determine effective rotation for dimension calculation
            const effectiveRotation = this.directPrintRotation !== 'default' 
                ? parseInt(this.directPrintRotation) 
                : (this.rotation || 0);
            // Swap width/height if rotation is 90 or 270 (image is now portrait)
            const swapDims = (effectiveRotation === 90 || effectiveRotation === 270);
            const printW = swapDims ? this.canvasHeight : this.canvasWidth;
            const printH = swapDims ? this.canvasWidth : this.canvasHeight;

            const printRes = await fetch(this.printAgentUrl + '/print', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_base64: base64,
                    width_mm: printW,
                    height_mm: printH,
                    copies: 1,
                    // ★ CALIBRATION: label_gap_mm — physical gap (brecha) between
                    // stickers on the roll.  The printer advances by
                    // (height_mm + label_gap_mm) after each label.
                    // Adjust this value if prints drift over 50+ labels:
                    //   Drift DOWN → increase (e.g. 3 → 3.5)
                    //   Drift UP   → decrease (e.g. 3 → 2.5)
                    // This value is also configurable server-side in
                    // print_agent_config.json → "label_gap_mm".
                    // If omitted here, the print agent uses its config default.
                    label_gap_mm: 3
                })
            });

            const printData = await printRes.json();
            if (printData.success) {
                this.directPrintMessage = '\u2705 Impreso correctamente en ' + this.printAgentPrinter + ' (' + printW + '\u00d7' + printH + 'mm, rot=' + effectiveRotation + '\u00b0)';
                this.directPrintError = false;
            } else {
                this.directPrintMessage = 'Error: ' + (printData.errors?.join(', ') || 'Fallo de impresi\u00f3n');
                this.directPrintError = true;
            }
        } catch (e) {
            this.directPrintMessage = 'Error de conexi\u00f3n: ' + e.message;
            this.directPrintError = true;
            console.error(e);
        } finally {
            this.directPrinting = false;
        }
    },

    async saveTemplate() {
        const payload = {
            id: this.templateId,
            name: this.templateName,
            width_mm: this.canvasWidth,
            height_mm: this.canvasHeight,
            rotation: this.rotation,
            elements: this.elements.map(el => {
                const { _uid, ...rest } = el;
                return rest;
            })
        };

        try {
            const resp = await fetch('/templates/api/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await resp.json();
            if (data.success) {
                this.templateId = data.template.id;
                this.dirty = false;
                this.saveMessage = '✅ Plantilla guardada exitosamente';
                this.saveError = false;
                // Update URL without reload
                window.history.replaceState({}, '', '/templates/designer/' + data.template.id);
            } else {
                this.saveMessage = '❌ ' + (data.error || 'Error al guardar');
                this.saveError = true;
            }
        } catch (e) {
            this.saveMessage = '❌ Error: ' + e.message;
            this.saveError = true;
        }

        setTimeout(() => { this.saveMessage = ''; }, 3000);
    },

    // ═══ Quick Start Preset ═══
    loadPreset() {
        if (this.elements.length > 0 && !confirm('Esto reemplazará los elementos actuales. ¿Continuar?')) return;

        this.canvasWidth = (this.templateName === 'Almacen2' || '1' === 'Almacen2') ? 200 : 151;
        this.canvasHeight = (this.templateName === 'Almacen2' || '1' === 'Almacen2') ? 150 : 101;
            // Header section
            { _uid: this.nextUid(), type: 'barcode', field: 'process_barcode', x_mm: 3, y_mm: 3, width_mm: 45, font_size: 7, bar_height_mm: 8, bar_width: 1, show_text: true, font_weight: 'normal', alignment: 'left', color: '#000000' },
            { _uid: this.nextUid(), type: 'barcode', field: 'internal_code_barcode', x_mm: 145, y_mm: 3, width_mm: 50, font_size: 7, bar_height_mm: 7, bar_width: 1.25, show_text: true, font_weight: 'normal', alignment: 'left', color: '#000000' },
            { _uid: this.nextUid(), type: 'text', field: 'product_name', x_mm: 20, y_mm: 17, width_mm: 160, font_size: 18, font_weight: 'bold', alignment: 'center', color: '#000000' },
            { _uid: this.nextUid(), type: 'text', field: 'signal_word', x_mm: 150, y_mm: 22, width_mm: 45, font_size: 13, font_weight: 'bold', alignment: 'right', color: '#dc2626' },
            { _uid: this.nextUid(), type: 'text', field: 'cas_number', x_mm: 3, y_mm: 22, width_mm: 50, font_size: 6, font_weight: 'normal', alignment: 'left', color: '#000000' },

            // Separator
            { _uid: this.nextUid(), type: 'line', field: 'separator_line', x_mm: 3, y_mm: 25, width_mm: 194, line_width: 0.5, color: '#000000' },

            // Content section
            { _uid: this.nextUid(), type: 'static', field: 'h_header', x_mm: 3, y_mm: 28, width_mm: 65, font_size: 7, font_weight: 'bold', alignment: 'left', color: '#000000', custom_text: 'INDICACIONES DE PELIGRO:' },
            { _uid: this.nextUid(), type: 'multiline', field: 'h_statements', x_mm: 3, y_mm: 32, width_mm: 65, font_size: 5.5, font_weight: 'normal', alignment: 'left', color: '#000000' },
            { _uid: this.nextUid(), type: 'static', field: 'p_header', x_mm: 3, y_mm: 60, width_mm: 65, font_size: 7, font_weight: 'bold', alignment: 'left', color: '#000000', custom_text: 'CONSEJOS DE PRUDENCIA:' },
            { _uid: this.nextUid(), type: 'multiline', field: 'p_statements', x_mm: 3, y_mm: 64, width_mm: 65, font_size: 5, font_weight: 'normal', alignment: 'left', color: '#000000' },

            // Bottom separator
            { _uid: this.nextUid(), type: 'line', field: 'separator_line', x_mm: 3, y_mm: 102, width_mm: 194, line_width: 1, color: '#000000' },

            // Bottom left: dates and batch
            { _uid: this.nextUid(), type: 'static', field: 'elab_date_label', x_mm: 1, y_mm: 116, width_mm: 30, font_size: 7, font_weight: 'bold', alignment: 'left', color: '#000000', custom_text: 'F.ELABORACION:' },
            { _uid: this.nextUid(), type: 'text', field: 'elab_date_value', x_mm: 31, y_mm: 115, width_mm: 45, font_size: 16, font_weight: 'bold', alignment: 'left', color: '#000000' },
            { _uid: this.nextUid(), type: 'static', field: 'reinsp_date_label', x_mm: 1, y_mm: 128, width_mm: 30, font_size: 7, font_weight: 'bold', alignment: 'left', color: '#000000', custom_text: 'F.REINSPECCION:' },
            { _uid: this.nextUid(), type: 'text', field: 'reinsp_date_value', x_mm: 31, y_mm: 127, width_mm: 45, font_size: 16, font_weight: 'bold', alignment: 'left', color: '#000000' },
            { _uid: this.nextUid(), type: 'static', field: 'lote_label', x_mm: 87, y_mm: 116, width_mm: 20, font_size: 10, font_weight: 'bold', alignment: 'left', color: '#000000', custom_text: 'LOTE:' },
            { _uid: this.nextUid(), type: 'text', field: 'lote_value', x_mm: 80, y_mm: 128, width_mm: 55, font_size: 15, font_weight: 'bold', alignment: 'left', color: '#000000' },
            { _uid: this.nextUid(), type: 'barcode', field: 'batch_barcode', x_mm: 50, y_mm: 140, width_mm: 55, font_size: 7, bar_height_mm: 4, bar_width: 1.25, show_text: false, font_weight: 'normal', alignment: 'left', color: '#000000' },

            // Bottom right: weights
            { _uid: this.nextUid(), type: 'line', field: 'separator_line', x_mm: 140, y_mm: 102, width_mm: 0.5, line_width: 50, color: '#000000' },
            { _uid: this.nextUid(), type: 'static', field: 'peso_bruto_label', x_mm: 142, y_mm: 107, width_mm: 25, font_size: 7, font_weight: 'bold', alignment: 'left', color: '#000000', custom_text: 'PESO BRUTO:' },
            { _uid: this.nextUid(), type: 'text', field: 'peso_bruto_value', x_mm: 165, y_mm: 106, width_mm: 30, font_size: 14, font_weight: 'bold', alignment: 'right', color: '#000000' },
            { _uid: this.nextUid(), type: 'static', field: 'peso_tara_label', x_mm: 142, y_mm: 118, width_mm: 25, font_size: 7, font_weight: 'bold', alignment: 'left', color: '#000000', custom_text: 'PESO TARA:' },
            { _uid: this.nextUid(), type: 'text', field: 'peso_tara_value', x_mm: 165, y_mm: 117, width_mm: 30, font_size: 14, font_weight: 'bold', alignment: 'right', color: '#000000' },
            { _uid: this.nextUid(), type: 'static', field: 'peso_neto_label', x_mm: 142, y_mm: 129, width_mm: 25, font_size: 7, font_weight: 'bold', alignment: 'left', color: '#000000', custom_text: 'PESO NETO:' },
            { _uid: this.nextUid(), type: 'barcode', field: 'net_weight_barcode', x_mm: 155, y_mm: 133, width_mm: 30, font_size: 10, bar_height_mm: 4, bar_width: 0.9, show_text: true, font_weight: 'bold', alignment: 'center', color: '#000000' },

            // Footer
            { _uid: this.nextUid(), type: 'static', field: 'address_footer', x_mm: 5, y_mm: 150, width_mm: 190, font_size: 7, font_weight: 'normal', alignment: 'center', color: '#000000', custom_text: 'QUIMICA BOSS San Agustin 759 Col. El Briseño, Zapopan, Jalisco, México. CP 45236 Tel: 36 84 05 05' },
        ];

        this.selectedElement = null;
        this.markDirty();
        this.$nextTick(() => this.autoZoom());
    },
    };
}
