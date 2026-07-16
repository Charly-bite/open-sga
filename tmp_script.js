
function controlInterno() {
    return {
        // Data
        products: [],
        containers: [],
        productTypes: [],
        loading: false,
        searchQuery: '',
        filterType: '',
        filterStatus: '',
        currentPage: 1,
        perPage: 50,
        totalProducts: 0,
        totalPages: 0,
        selectedIds: [],
        bulkType: '',
        summaryData: {},

        // Detail modal
        mainTab: 'clasificacion',
        loteHistory: [],
        loteHistoryLoading: false,
        editingLoteId: null,
        editLoteValue: '',

        showDetailModal: false,
        modalTab: 'general',
        detailProduct: {},
        newTaraNeto: '',
        newTaraVal: '',

        // Toast
        toastMessage: '',

        init() {
            this.loadContainers();
            this.loadProductTypes();
            this.loadProducts(1);
        },

        async loadContainers() {
            try {
                const res = await fetch('/control/api/containers');
                this.containers = await res.json();
            } catch (e) { console.error('Error loading containers:', e); }
        },

        async loadProductTypes() {
            try {
                const res = await fetch('/control/api/product-types');
                this.productTypes = await res.json();
            } catch (e) { console.error('Error loading product types:', e); }
        },

        async loadProducts(page) {
            if (page < 1) return;
            this.loading = true;
            this.currentPage = page;
            try {
                const params = new URLSearchParams({
                    page: page,
                    per_page: this.perPage,
                    search: this.searchQuery,
                    product_type: this.filterType,
                    status: this.filterStatus
                });
                const res = await fetch(`/control/api/products?${params}`);
                const data = await res.json();
                this.products = data.products || [];
                this.totalProducts = data.total || 0;
                this.totalPages = data.total_pages || 0;
            } catch (e) {
                console.error('Error loading products:', e);
            }
            this.loading = false;
        },

        
        async saveInlineLote(product) {
            if (this.editLoteValue === product.lote) {
                this.editingLoteId = null;
                return;
            }
            try {
                const res = await fetch(`/control/api/products/${product.product_id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ lote: this.editLoteValue })
                });
                const data = await res.json();
                if (data.success) {
                    product.lote = this.editLoteValue;
                    this.toast('✅ Lote actualizado exitosamente');
                    // refresh lote history if it's the active tab implicitly
                    if (this.mainTab === 'historial_lotes') {
                        this.loadLoteHistory();
                    }
                }
            } catch (e) {
                console.error('Error saving inline lote:', e);
                this.toast('❌ Error al actualizar el lote', 'error');
            }
            this.editingLoteId = null;
        },

        async loadLoteHistory() {
            this.loteHistoryLoading = true;
            try {
                const res = await fetch('/control/api/lote-history?page=1&per_page=100');
                if (!res.ok) throw new Error('Error en API');
                const data = await res.json();
                this.loteHistory = data.history || [];
            } catch (e) {
                console.error(e);
            }
            this.loteHistoryLoading = false;
        },

        async loadSummary() {
            try {
                const res = await fetch('/control/api/summary');
                this.summaryData = await res.json();
            } catch (e) { console.error(e); }
        },

        async updateProductType(productId, value) {
            try {
                await fetch(`/control/api/products/${productId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product_type: value })
                });
                // Update local state
                const p = this.products.find(x => x.product_id === productId);
                if (p) { p.product_type = value; p.type_source = 'manual'; }
                this.loadSummary();
                this.toast('✅ Tipo actualizado');
            } catch (e) {
                console.error('Error updating type:', e);
            }
        },

        async updateProductContainer(productId, value) {
            try {
                await fetch(`/control/api/products/${productId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ default_container: value })
                });
                const p = this.products.find(x => x.product_id === productId);
                if (p) p.default_container = value;
                this.toast('✅ Envase actualizado');
            } catch (e) {
                console.error('Error updating container:', e);
            }
        },

        async bulkUpdateType() {
            if (!this.bulkType || this.selectedIds.length === 0) return;
            try {
                const res = await fetch('/control/api/bulk-update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        product_ids: this.selectedIds,
                        product_type: this.bulkType
                    })
                });
                const data = await res.json();
                if (data.success) {
                    this.toast(`✅ ${data.updated} productos actualizados`);
                    this.selectedIds = [];
                    this.bulkType = '';
                    this.loadProducts(this.currentPage);
                    this.loadSummary();
                }
            } catch (e) {
                console.error('Error bulk updating:', e);
            }
        },

        async autoClassify() {
            try {
                const res = await fetch('/control/api/auto-classify', { method: 'POST' });
                const data = await res.json();
                this.toast(`⚡ ${data.classified} productos auto-clasificados`);
                this.loadProducts(this.currentPage);
                this.loadSummary();
            } catch (e) {
                console.error('Error auto-classifying:', e);
            }
        },

        async openDetail(productId) {
            this.newTaraNeto = '';
            this.newTaraVal = '';
            try {
                const res = await fetch(`/control/api/products/${productId}`);
                let dp = await res.json();
                if (dp.tara_history) {
                    dp.tara_history.forEach(t => {
                        if (t.tara_kg < 0) t.deleted = true;
                    });
                }
                this.detailProduct = dp;
                this.showDetailModal = true;
            } catch (e) {
                console.error('Error loading detail:', e);
            }
        },
        
        addTaraOverride() {
            if (!this.newTaraNeto || !this.newTaraVal) return;
            const neto = parseFloat(this.newTaraNeto);
            const tara = parseFloat(this.newTaraVal);
            if (isNaN(neto) || isNaN(tara)) return;
            
            if (!this.detailProduct.tara_history) {
                this.detailProduct.tara_history = [];
            }
            
            const existingIdx = this.detailProduct.tara_history.findIndex(t => t.peso_neto === neto);
            if (existingIdx >= 0) {
                this.detailProduct.tara_history[existingIdx].tara_kg = tara;
                this.detailProduct.tara_history[existingIdx].deleted = false;
            } else {
                this.detailProduct.tara_history.push({ peso_neto: neto, tara_kg: tara });
                this.detailProduct.tara_history.sort((a,b) => a.peso_neto - b.peso_neto);
            }
            
            this.newTaraNeto = '';
            this.newTaraVal = '';
        },
        
        removeTara(neto) {
            if (!this.detailProduct.tara_history) return;
            // Instead of completely removing, mark as deleted so backend knows
            const idx = this.detailProduct.tara_history.findIndex(t => t.peso_neto === neto);
            if (idx >= 0) {
                this.detailProduct.tara_history[idx].deleted = true;
            }
        },

        async saveDetail() {
            try {
                let overrides = {};
                // Include original overrides, we must preserve what was there or deleted
                // But honestly, whatever is in detailProduct.tara_history is the ground truth
                if (this.detailProduct.tara_history && this.detailProduct.tara_history.length > 0) {
                    this.detailProduct.tara_history.forEach(t => {
                        if (t.deleted) {
                            overrides[t.peso_neto.toString()] = -1; // -1 signifies deleted
                        } else {
                            overrides[t.peso_neto.toString()] = parseFloat(t.tara_kg);
                        }
                    });
                }
                
                const res = await fetch(`/control/api/products/${this.detailProduct.product_id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        product_type: this.detailProduct.product_type,
                        default_container: this.detailProduct.default_container,
                        notes: this.detailProduct.notes,
                        lote: this.detailProduct.lote,
                        tara_overrides: overrides
                    })
                });
                const data = await res.json();
                if (data.success) {
                    this.showDetailModal = false;
                    this.toast('✅ Cambios guardados');
                    this.loadProducts(this.currentPage);
                    this.loadSummary();
                }
            } catch (e) {
                console.error('Error saving detail:', e);
            }
        },

        toggleSelectAll(event) {
            if (event.target.checked) {
                this.selectedIds = this.products.map(p => p.product_id);
            } else {
                this.selectedIds = [];
            }
        },

        paginationRange() {
            const total = this.totalPages;
            const current = this.currentPage;
            const range = [];
            if (total <= 7) {
                for (let i = 1; i <= total; i++) range.push(i);
            } else {
                range.push(1);
                if (current > 3) range.push('...');
                for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
                    range.push(i);
                }
                if (current < total - 2) range.push('...');
                range.push(total);
            }
            return range;
        },

        toast(message) {
            this.toastMessage = message;
            setTimeout(() => { this.toastMessage = ''; }, 3000);
        }
    };
}
