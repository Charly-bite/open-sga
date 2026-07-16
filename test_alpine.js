{% extends "base.html" %}

{% block title %}Control Interno{% endblock %}
{% block page_title %}Control Interno — Clasificación de Productos{% endblock %}

{% block content %}
<div x-data="controlInterno()" x-init="init()">

    
    <!-- Top Level Tabs -->
    <div class="bg-white rounded-xl shadow-sm mb-6 overflow-hidden">
        <div class="flex border-b border-slate-200">
            <button @click="mainTab = 'clasificacion'" 
                    class="flex-1 py-4 text-sm font-medium transition-colors focus:outline-none"
                    :class="mainTab === 'clasificacion' ? 'border-b-2 border-blue-600 text-blue-600 bg-blue-50/50' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'">
                <div class="flex items-center justify-center gap-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
                    Clasificación General
                </div>
            </button>
            <button @click="mainTab = 'historial_lotes'" 
                    class="flex-1 py-4 text-sm font-medium transition-colors focus:outline-none"
                    :class="mainTab === 'historial_lotes' ? 'border-b-2 border-blue-600 text-blue-600 bg-blue-50/50' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'">
                <div class="flex items-center justify-center gap-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    Historial de Lotes
                </div>
            </button>
        </div>
    </div>

    <!-- VIEW 1: Clasificacion -->
    <div x-show="mainTab === 'clasificacion'">

    <!-- Summary Cards -->
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        <div class="bg-white rounded-xl shadow-sm p-4 border-l-4 border-blue-500">
            <div class="text-2xl font-bold text-slate-800" x-text="summaryData.total_products || '{{ stats.total_products }}'">{{ stats.total_products }}</div>
            <div class="text-xs text-slate-500 mt-1">Total Productos</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 border-l-4 border-cyan-500">
            <div class="text-2xl font-bold text-cyan-700" x-text="summaryData.liquido || '{{ summary.liquido }}'">{{ summary.liquido }}</div>
            <div class="text-xs text-slate-500 mt-1">💧 Líquidos</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 border-l-4 border-purple-500">
            <div class="text-2xl font-bold text-purple-700" x-text="summaryData.pasta || '{{ summary.pasta }}'">{{ summary.pasta }}</div>
            <div class="text-xs text-slate-500 mt-1">🫧 Pasta / Gel</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 border-l-4 border-amber-500">
            <div class="text-2xl font-bold text-amber-700" x-text="summaryData.polvo || '{{ summary.polvo }}'">{{ summary.polvo }}</div>
            <div class="text-xs text-slate-500 mt-1">🧂 Polvo</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 border-l-4 border-teal-500">
            <div class="text-2xl font-bold text-teal-700" x-text="summaryData.solido || '{{ summary.solido }}'">{{ summary.solido }}</div>
            <div class="text-xs text-slate-500 mt-1">🧊 Sólidos</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 border-l-4 border-red-400">
            <div class="text-2xl font-bold text-red-600" x-text="summaryData.sin_clasificar || '{{ summary.sin_clasificar }}'">{{ summary.sin_clasificar }}</div>
            <div class="text-xs text-slate-500 mt-1">❓ Sin Clasificar</div>
        </div>
    </div>

    <!-- Filters & Actions Bar -->
    <div class="bg-white rounded-xl shadow-sm p-4 mb-6">
        <div class="flex flex-wrap items-end gap-3">
            <!-- Search -->
            <div class="flex-1 min-w-[250px]">
                <label class="block text-xs font-medium text-slate-500 mb-1">Buscar</label>
                <input type="text" x-model="searchQuery" @input.debounce.400ms="loadProducts(1)"
                    placeholder="Código o nombre del producto..."
                    class="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm">
            </div>

            <!-- Product Type Filter -->
            <div class="w-44">
                <label class="block text-xs font-medium text-slate-500 mb-1">Tipo Producto</label>
                <select x-model="filterType" @change="loadProducts(1)"
                    class="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500 text-sm">
                    <option value="">Todos</option>
                    <option value="liquido">💧 Líquido</option>
                    <option value="pasta">🫧 Pasta / Gel</option>
                    <option value="polvo">🧂 Polvo</option>
                    <option value="solido">🧊 Sólido</option>
                </select>
            </div>

            <!-- Status Filter -->
            <div class="w-40">
                <label class="block text-xs font-medium text-slate-500 mb-1">Estado</label>
                <select x-model="filterStatus" @change="loadProducts(1)"
                    class="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500 text-sm">
                    <option value="">Todos</option>
                    <option value="classified">✅ Clasificados</option>
                    <option value="unclassified">❓ Sin clasificar</option>                      <option value="lote">📦 Con Lote</option>
                      <option value="sin_lote">🚫 Sin Lote</option>
                      <option value="atencion">⚠️ Atención (Vencimiento)</option>                </select>
            </div>

            <!-- Bulk Actions -->
            <div x-show="selectedIds.length > 0" class="flex items-end gap-2" x-cloak>
                <div class="px-3 py-2 bg-blue-50 rounded-lg text-sm text-blue-700 font-medium">
                    <span x-text="selectedIds.length"></span> seleccionados
                </div>
                <select x-model="bulkType" class="px-3 py-2 rounded-lg border border-slate-300 text-sm">
                    <option value="">Asignar tipo...</option>
                    <option value="liquido">💧 Líquido</option>
                    <option value="pasta">🫧 Pasta / Gel</option>
                    <option value="polvo">🧂 Polvo</option>
                    <option value="solido">🧊 Sólido</option>
                </select>
                <button @click="bulkUpdateType()" :disabled="!bulkType"
                    class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm transition-colors">
                    Aplicar
                </button>
            </div>

            <!-- Auto-classify Button -->
            <button @click="autoClassify()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm transition-colors flex items-center gap-1.5">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Auto-clasificar
            </button>
        </div>
    </div>

    <!-- Products Table -->
    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
        <!-- Header -->
        <div class="px-6 py-3 border-b border-slate-200 flex items-center justify-between bg-slate-50">
            <span class="text-sm text-slate-600">
                <span x-text="totalProducts"></span> productos
                <span x-show="totalPages > 1" class="text-slate-400">
                    — Página <span x-text="currentPage"></span> de <span x-text="totalPages"></span>
                </span>
            </span>
            <!-- Pagination -->
            <div class="flex items-center gap-1" x-show="totalPages > 1">
                <button @click="loadProducts(currentPage - 1)" :disabled="currentPage <= 1"
                    class="px-3 py-1 text-sm rounded border hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed">←</button>
                <template x-for="p in paginationRange()" :key="p">
                    <button @click="if(p !== '...') loadProducts(p)"
                        :class="p === currentPage ? 'bg-blue-600 text-white border-blue-600' : 'hover:bg-slate-100'"
                        class="px-3 py-1 text-sm rounded border transition-colors"
                        x-text="p"></button>
                </template>
                <button @click="loadProducts(currentPage + 1)" :disabled="currentPage >= totalPages"
                    class="px-3 py-1 text-sm rounded border hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed">→</button>
            </div>
        </div>

        <!-- Table -->
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead class="bg-slate-50 border-b">
                    <tr class="text-left text-xs text-slate-500 uppercase tracking-wider">
                        <th class="pl-6 pr-2 py-3 w-10">
                            <input type="checkbox" @change="toggleSelectAll($event)" :checked="selectedIds.length === products.length && products.length > 0"
                                class="rounded border-slate-300 text-blue-600 focus:ring-blue-500">
                        </th>
                        <th class="px-4 py-3">Código</th>
                        <th class="px-4 py-3">Nombre Químico</th>
                        <th class="px-4 py-3">Lotes</th>
                        <th class="px-4 py-3 w-40">Tipo Producto</th>
                        <th class="px-4 py-3 w-48">Envase por Defecto</th>
                        <th class="px-4 py-3 w-64">Pesos Tara Conocidos</th>
                        <th class="px-4 py-3 w-32">Fuente</th>
                        <th class="px-4 py-3 w-20 text-right">Acciones</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                    <template x-if="loading">
                        <tr>
                            <td colspan="9" class="px-6 py-12 text-center text-slate-400">
                                <svg class="animate-spin h-6 w-6 mx-auto mb-2 text-blue-500" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                                </svg>
                                Cargando...
                            </td>
                        </tr>
                    </template>
                    <template x-if="!loading && products.length === 0">
                        <tr>
                            <td colspan="9" class="px-6 py-12 text-center text-slate-400">No se encontraron productos</td>
                        </tr>
                    </template>
                    <template x-for="product in products" :key="product.product_id">
                        <tr class="hover:bg-slate-50/50 transition-colors" :class="selectedIds.includes(product.product_id) ? 'bg-blue-50/40' : ''">
                            <!-- Checkbox -->
                            <td class="pl-6 pr-2 py-3">
                                <input type="checkbox" :value="product.product_id" x-model="selectedIds"
                                    class="rounded border-slate-300 text-blue-600 focus:ring-blue-500">
                            </td>
                            <!-- Code -->
                            <td class="px-4 py-3">
                                <span class="font-mono text-sm font-semibold text-slate-700" x-text="product.product_id"></span>
                            </td>
                            <!-- Name -->
                            <td class="px-4 py-3">
                                <span class="text-sm text-slate-800" x-text="product.chemical_name || '—'"></span>
                            </td>
                            
                            <!-- Lote -->
                            <td class="px-4 py-3" @dblclick="editingLoteId = product.product_id; editLoteValue = product.lote || ''; editLoteDateValue = product.lote_date || ''; editLoteReinspDateValue = product.lote_reinspection_date || ''; editMermaValue = ''; editNotesValue = ''; autoFillInlineReinspectionFromElab()">
                                <template x-if="editingLoteId !== product.product_id">
                                    <div class="cursor-pointer group relative inline-block">
                                        <div class="inline-flex flex-col items-start">
                                            <span class="text-sm px-2 py-1 rounded border transition-colors inline-block" 
                                                  :class="product.requires_attention ? 'text-red-700 bg-red-100 border-red-300 shadow-sm' : 'text-slate-600 bg-slate-100 border-transparent group-hover:border-slate-300'"
                                                  x-show="product.lote" x-text="product.lote"></span>
                                            <span class="text-[10px] text-slate-400 mt-0.5 ml-1" x-show="product.lote && product.lote_date" x-text="'F.Elaboracion: ' + product.lote_date"></span>
                                            <span class="text-[10px] text-slate-400 mt-0.5 ml-1" x-show="product.lote && product.lote_reinspection_date" x-text="'F.Reinspeccion: ' + product.lote_reinspection_date"></span>
                                        </div>
                                        <div x-show="product.requires_attention && product.lote" class="text-[10px] text-red-500 mt-1 font-semibold leading-tight whitespace-nowrap">
                                            (Producto necesita atención)
                                        </div>
                                        <span class="text-sm text-slate-400 border-b border-dashed border-slate-300 px-1 hover:text-slate-600 transition-colors" x-show="!product.lote">Asignar lote...</span>
                                        <div class="absolute -top-8 left-1/2 -translate-x-1/2 bg-black text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">Doble click para editar</div>
                                    </div>
                                </template>
                                <template x-if="editingLoteId === product.product_id">
                                    <div class="flex flex-col gap-1 w-56">
                                        <input type="text" x-model="editLoteValue" placeholder="Lote" @keyup.enter="saveInlineLote(product)" @keydown.escape="editingLoteId = null" x-init="$el.focus()"
                                            class="w-full px-2 py-1 text-sm rounded bg-white border-2 border-blue-500 shadow-inner focus:outline-none placeholder-slate-300">
                                        <div class="flex items-center gap-1">
                                            <label class="text-[10px] text-slate-500 font-semibold w-20">F.Elaboracion</label>
                                            <input type="date" x-model="editLoteDateValue" title="F.Elaboracion" @change="autoFillInlineReinspectionFromElab()" @keyup.enter="saveInlineLote(product)" @keydown.escape="editingLoteId = null"
                                                class="flex-1 px-2 py-1 text-xs rounded bg-white border-2 border-blue-500 shadow-inner focus:outline-none">
                                        </div>
                                        <div class="flex items-center gap-1">
                                            <label class="text-[10px] text-slate-500 font-semibold w-20">F.Reinspeccion</label>
                                            <input type="date" x-model="editLoteReinspDateValue" title="F.Reinspeccion" @keyup.enter="saveInlineLote(product)" @keydown.escape="editingLoteId = null"
                                                class="flex-1 px-2 py-1 text-xs rounded bg-white border-2 border-blue-500 shadow-inner focus:outline-none">
                                            <button @click="saveInlineLote(product)" class="p-1 text-emerald-600 hover:bg-emerald-50 rounded" title="Guardar"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg></button>
                                            <button @click="editingLoteId = null" class="p-1 text-red-600 hover:bg-red-50 rounded" title="Cancelar"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>
                                        </div>
                                        <div class="flex items-center gap-1 mt-1">
                                            <label class="text-[10px] text-slate-500 font-semibold w-20">Merma (kg)</label>
                                            <input type="number" step="0.01" min="0" x-model="editMermaValue" title="Peso de merma" placeholder="0.00" @keyup.enter="saveInlineLote(product)" @keydown.escape="editingLoteId = null"
                                                class="flex-1 px-2 py-1 text-xs rounded bg-white border-2 border-orange-400 shadow-inner focus:outline-none placeholder-slate-300">
                                        </div>
                                        <div class="flex items-center gap-1 mt-1">
                                            <label class="text-[10px] text-slate-500 font-semibold w-20">Notas</label>
                                            <input type="text" x-model="editNotesValue" title="Notas u observaciones" placeholder="Opcional..." @keyup.enter="saveInlineLote(product)" @keydown.escape="editingLoteId = null"
                                                class="flex-1 px-2 py-1 text-xs rounded bg-white border-2 border-slate-300 shadow-inner focus:outline-none placeholder-slate-300">
                                        </div>
                                    </div>
                                </template>
                            </td>
                            <!-- Product Type Selector -->
                            <td class="px-4 py-3">
                                <select :value="product.product_type || ''"
                                    @change="updateProductType(product.product_id, $event.target.value)"
                                    class="w-full px-2 py-1.5 text-sm rounded-lg border transition-colors"
                                    :class="product.product_type
                                        ? 'border-emerald-300 bg-emerald-50/50'
                                        : 'border-red-300 bg-red-50/50'">
                                    <option value="">— Sin tipo —</option>
                                    <option value="liquido">💧 Líquido</option>
                                    <option value="pasta">🫧 Pasta / Gel</option>
                                    <option value="polvo">🧂 Polvo</option>
                                    <option value="solido">🧊 Sólido</option>
                                </select>
                            </td>
                            <!-- Default Container -->
                            <td class="px-4 py-3">
                                <select :value="product.default_container || ''"
                                    @change="updateProductContainer(product.product_id, $event.target.value)"
                                    class="w-full px-2 py-1.5 text-sm rounded-lg border border-slate-200 bg-slate-50/50">
                                    <option value="">— Automático —</option>
                                    <template x-for="c in containers" :key="c.id">
                                        <option :value="c.id" x-text="`${c.name} (${c.tara_kg} kg)`"></option>
                                    </template>
                                </select>
                            </td>
                            <!-- Known Tara Weights -->
                            <td class="px-4 py-3">
                                <div class="flex flex-wrap gap-1">
                                    <template x-if="product.tara_history && product.tara_history.length > 0">
                                        <template x-for="th in product.tara_history.slice(0, 5)" :key="th.peso_neto">
                                            <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-100 text-slate-600 border border-slate-200"
                                                :title="`Peso Neto: ${th.peso_neto} kg → Tara: ${th.tara_kg} kg`">
                                                <span x-text="th.peso_neto + 'kg'"></span>
                                                <span class="mx-0.5 text-slate-400">→</span>
                                                <span class="font-semibold" x-text="th.tara_kg + 'kg'"></span>
                                            </span>
                                        </template>
                                    </template>
                                    <template x-if="!product.tara_history || product.tara_history.length === 0">
                                        <span class="text-xs text-slate-400">Sin datos</span>
                                    </template>
                                    <template x-if="product.tara_history && product.tara_history.length > 5">
                                        <span class="text-[10px] text-slate-400" x-text="`+${product.tara_history.length - 5} más`"></span>
                                    </template>
                                </div>
                            </td>
                            <!-- Source -->
                            <td class="px-4 py-3">
                                <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
                                    :class="product.type_source === 'manual'
                                        ? 'bg-blue-100 text-blue-700'
                                        : product.type_source === 'auto'
                                            ? 'bg-amber-100 text-amber-700'
                                            : 'bg-slate-100 text-slate-500'"
                                    x-text="product.type_source === 'manual' ? '✋ Manual' : product.type_source === 'auto' ? '⚡ Auto' : '—'">
                                </span>
                            </td>
                            <!-- Actions -->
                            <td class="px-4 py-3 text-right">
                                <button @click="openDetail(product.product_id)"
                                    class="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                                    title="Ver detalle">
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                    </svg>
                                </button>
                            </td>
                        </tr>
                    </template>
                </tbody>
            </table>
        </div>

        <!-- Bottom Pagination -->
        <div class="px-6 py-3 border-t border-slate-200 flex items-center justify-between bg-slate-50" x-show="totalPages > 1">
            <span class="text-sm text-slate-500">
                Mostrando <span x-text="((currentPage-1)*perPage)+1"></span>-<span x-text="Math.min(currentPage*perPage, totalProducts)"></span> de <span x-text="totalProducts"></span>
            </span>
            <div class="flex items-center gap-1">
                <button @click="loadProducts(currentPage - 1)" :disabled="currentPage <= 1"
                    class="px-3 py-1 text-sm rounded border hover:bg-slate-100 disabled:opacity-40">←</button>
                <button @click="loadProducts(currentPage + 1)" :disabled="currentPage >= totalPages"
                    class="px-3 py-1 text-sm rounded border hover:bg-slate-100 disabled:opacity-40">→</button>
            </div>
        </div>
    </div>

    
    </div> <!-- End View 1 -->

    <!-- VIEW 2: Historial Lotes -->
    <div x-show="mainTab === 'historial_lotes'" x-cloak>
        <div class="bg-white rounded-xl shadow-sm overflow-hidden border border-slate-200">
            <div class="px-6 py-4 border-b border-slate-200 flex justify-between items-center bg-slate-50/50">
                <h3 class="text-lg font-bold text-slate-800">Control de Mermas (Últimos Movimientos de Lote)</h3>
                <div class="flex items-center gap-3">
                      <a href="/labels/export/lotes_modificados" target="_blank" class="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors" title="Descargar reporte de lotes modificados en Excel">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                        Exportar Reporte
                    </a>
                    <button @click="loadLoteHistory()" class="text-slate-400 hover:text-blue-600 transition-colors" title="Actualizar historial">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                    </button>
                </div>
            </div>
            <div class="p-0">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                            <th class="px-6 py-3 w-40">Fecha</th>
                            <th class="px-6 py-3 w-32">Usuario</th>
                            <th class="px-6 py-3 w-48">Producto</th>
                            <th class="px-6 py-3">Cambio de Lote</th>
                            <th class="px-6 py-3 w-48">Notas</th>
                            <th class="px-6 py-3 w-32">Merma</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100 text-sm">
                        <template x-if="loteHistoryLoading">
                            <tr><td colspan="6" class="px-6 py-12 text-center text-slate-400">Cargando historial...</td></tr>
                        </template>
                        <template x-if="!loteHistoryLoading && loteHistory.length === 0">
                            <tr><td colspan="6" class="px-6 py-12 text-center text-slate-400">No hay movimientos recientes registrados.</td></tr>
                        </template>
                        <template x-for="item in loteHistory" :key="(item.date || item.timestamp || '') + item.product_id">
                            <tr class="hover:bg-slate-50/50 transition-colors">
                                <td class="px-6 py-4 text-slate-500 whitespace-nowrap" x-text="item.date || item.timestamp"></td>
                                <td class="px-6 py-4 font-medium text-slate-700" x-text="item.user"></td>
                                <td class="px-6 py-4">
                                    <div class="font-mono font-semibold text-blue-700" x-text="item.product_id"></div>
                                    <div class="text-xs text-slate-500 truncate max-w-xs" x-text="item.chemical_name"></div>
                                </td>
                                <td class="px-6 py-4">
                                    <div class="flex items-center gap-3">
                                        <div class="flex flex-col items-center">
                                            <span class="inline-flex items-center px-2 py-1 bg-red-50 text-red-700 rounded text-xs font-mono line-through" x-text="item.old_lote || '(Vacio)'"></span>
                                            <span class="text-[10px] text-slate-400 mt-0.5 line-through" x-show="item.old_elab_date || item.old_date" x-text="'F.Elaboracion: ' + (item.old_elab_date || item.old_date)"></span>
                                            <span class="text-[10px] text-slate-400 mt-0.5 line-through" x-show="item.old_reinsp_date" x-text="'F.Reinspeccion: ' + item.old_reinsp_date"></span>
                                        </div>
                                        <svg class="w-4 h-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                                        <div class="flex flex-col items-center">
                                            <span class="inline-flex items-center px-2 py-1 bg-emerald-50 text-emerald-700 rounded text-xs font-mono font-bold" x-text="item.new_lote || '(Vacio)'"></span>
                                            <span class="text-[10px] text-slate-500 mt-0.5" x-show="item.new_elab_date || item.new_date" x-text="'F.Elaboracion: ' + (item.new_elab_date || item.new_date)"></span>
                                            <span class="text-[10px] text-slate-500 mt-0.5" x-show="item.new_reinsp_date" x-text="'F.Reinspeccion: ' + item.new_reinsp_date"></span>
                                        </div>
                                    </div>
                                </td>
                                <td class="px-6 py-4" 
                                    @dblclick="editingHistoryNoteId = (item.date || item.timestamp) + '_' + item.product_id; editHistoryNoteValue = item.notes || ''">
                                    <template x-if="editingHistoryNoteId !== ((item.date || item.timestamp) + '_' + item.product_id)">
                                        <div class="cursor-pointer text-xs text-slate-600 border-b border-dashed border-slate-300 hover:text-slate-800" 
                                             x-text="item.notes || 'Agregar nota...'" title="Doble clic para editar nota"></div>
                                    </template>
                                    <template x-if="editingHistoryNoteId === ((item.date || item.timestamp) + '_' + item.product_id)">
                                        <div class="flex items-center gap-1">
                                            <input type="text" x-model="editHistoryNoteValue" @keyup.enter="saveHistoryNote(item)" @keydown.escape="editingHistoryNoteId = null" x-init="$el.focus()"
                                                class="w-full px-2 py-1 text-xs rounded border border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-500">
                                            <button @click="saveHistoryNote(item)" class="text-emerald-600 hover:bg-emerald-50 rounded p-0.5"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg></button>
                                        </div>
                                    </template>
                                </td>
                                <td class="px-6 py-4 font-bold text-orange-600">
                                    <span x-show="item.merma_kg" x-text="item.merma_kg + ' kg'"></span>
                                    <span x-show="!item.merma_kg" class="text-slate-300 font-normal">—</span>
                                </td>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>
        </div>
    </div> <!-- End View 2 -->

    <!-- Detail/Edit Modal -->

    <div x-show="showDetailModal" x-cloak class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" @click.self="showDetailModal = false">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" @click.stop>
            <!-- Modal Header -->
            <div class="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-gradient-to-r from-slate-50 to-white">
                <div>
                    <h3 class="text-lg font-bold text-slate-800" x-text="detailProduct.chemical_name || 'Producto'"></h3>
                    <p class="text-sm font-mono text-slate-500" x-text="detailProduct.product_id"></p>
                </div>
                <button @click="showDetailModal = false" class="p-2 hover:bg-slate-100 rounded-lg">
                    <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>

            <!-- Modal Tabs -->
            <div class="px-6 pt-3 border-b border-slate-200 flex items-center gap-6 bg-slate-50/50">
                <button @click="modalTab = 'general'" class="pb-3 text-sm font-semibold border-b-2 transition-colors" :class="modalTab === 'general' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'">Información General</button>
                <button @click="modalTab = 'lotes'" class="pb-3 text-sm font-semibold border-b-2 transition-colors" :class="modalTab === 'lotes' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'">Historial de Lotes</button>
            </div>

            <!-- Modal Body: General -->
            <div x-show="modalTab === 'general'" class="p-6 space-y-5">
                <!-- Basic Info Row -->
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">CAS</label>
                        <div class="text-sm text-slate-700 bg-slate-50 px-3 py-2 rounded-lg" x-text="detailProduct.cas_number || '—'"></div>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Palabra Señal</label>
                        <div class="text-sm text-slate-700 bg-slate-50 px-3 py-2 rounded-lg" x-text="detailProduct.signal_word || '—'"></div>
                    </div>
                </div>

                <!-- Product Type -->
                <div>
                    <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Tipo de Producto</label>
                    <div class="grid grid-cols-4 gap-2">
                        <template x-for="pt in productTypes" :key="pt.id">
                            <button @click="detailProduct.product_type = pt.id"
                                class="px-3 py-3 rounded-xl border-2 text-center transition-all"
                                :class="detailProduct.product_type === pt.id
                                    ? 'border-blue-500 bg-blue-50 shadow-sm'
                                    : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'">
                                <div class="text-xl mb-0.5" x-text="pt.icon"></div>
                                <div class="text-xs font-semibold" :class="detailProduct.product_type === pt.id ? 'text-blue-700' : 'text-slate-600'" x-text="pt.name"></div>
                            </button>
                        </template>
                    </div>
                </div>

                <!-- Default Container -->
                <div>
                    <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Envase por Defecto</label>
                    <select x-model="detailProduct.default_container"
                        class="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500">
                        <option value="">— Automático (según peso) —</option>
                        <template x-for="c in containers" :key="c.id">
                            <option :value="c.id" x-text="`${c.name} — ${c.tara_kg} kg (${c.material})`"></option>
                        </template>
                    </select>
                </div>

                <!-- Tara History -->
                <div>
                    <div class="flex items-center justify-between mb-2">
                        <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider">Historial de Pesos Tara</label>
                    </div>
                    
                    <div class="bg-slate-50 rounded-xl p-3 mb-3 border border-slate-200">
                        <template x-if="detailProduct.tara_history && detailProduct.tara_history.length > 0">
                            <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-3">
                                <template x-for="(th, index) in detailProduct.tara_history" :key="index">
                                    <div x-show="!th.deleted" class="bg-white rounded-lg px-3 py-2 border border-slate-200 flex items-center justify-between group relative">
                                        <div>
                                            <div class="text-[10px] text-slate-400">Neto</div>
                                            <div class="text-sm font-semibold text-slate-700" x-text="th.peso_neto + ' kg'"></div>
                                        </div>
                                        <svg class="w-4 h-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                                        </svg>
                                        <div class="text-right pr-4">
                                            <div class="text-[10px] text-slate-400">Tara</div>
                                            <div class="text-sm font-bold text-emerald-700" x-text="th.tara_kg + ' kg'"></div>
                                        </div>
                                        <button @click="removeTara(th.peso_neto)" type="button" 
                                            class="absolute right-1 top-1 bottom-1 w-6 hidden group-hover:flex items-center justify-center text-red-400 hover:text-red-600 hover:bg-red-50 rounded bg-white" title="Eliminar">
                                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                                        </button>
                                    </div>
                                </template>
                            </div>
                        </template>
                        <template x-if="!detailProduct.tara_history || detailProduct.tara_history.length === 0">
                            <div class="text-sm text-slate-400 py-4 text-center mb-3">
                                No hay historial de pesos tara para este producto
                            </div>
                        </template>
                        
                        <!-- Add New Tara Form -->
                        <div class="flex items-center gap-2 border-t border-slate-200 pt-3">
                            <div class="flex-1">
                                <input type="number" step="0.001" placeholder="Peso Neto (kg)" x-model="newTaraNeto" 
                                    class="w-full px-3 py-1.5 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500">
                            </div>
                            <span class="text-slate-400">→</span>
                            <div class="flex-1">
                                <input type="number" step="0.001" placeholder="Tara (kg)" x-model="newTaraVal" 
                                    class="w-full px-3 py-1.5 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-emerald-500">
                            </div>
                            <button type="button" @click="addTaraOverride()" class="px-3 py-1.5 bg-blue-100 text-blue-700 hover:bg-blue-200 rounded-lg text-sm font-medium transition-colors">
                                + Agregar
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Notes -->
                <div>
                    <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Notas</label>
                    <textarea x-model="detailProduct.notes" rows="2" placeholder="Notas adicionales..."
                        class="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none"></textarea>
                </div>
            </div>

            <!-- Modal Body: Lotes -->
            <div x-cloak x-show="modalTab === 'lotes'" class="p-6 space-y-5 h-full flex flex-col">
                <div>
                    <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Lote / Lotes Actuales</label>
                      <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
                        <input type="text" x-model="detailProduct.lote" placeholder="Ej. A123, B456" title="Lote"
                           class="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 outline-none">
                       <div>
                        <label class="block text-[10px] text-slate-500 font-semibold mb-1">F.Elaboracion</label>
                        <input type="date" x-model="detailProduct.lote_date" title="F.Elaboracion" @change="autoFillDetailReinspectionFromElab()"
                            class="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 outline-none">
                       </div>
                       <div>
                        <label class="block text-[10px] text-slate-500 font-semibold mb-1">F.Reinspeccion</label>
                        <input type="date" x-model="detailProduct.lote_reinspection_date" title="F.Reinspeccion"
                            class="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 outline-none">
                       </div>
                    </div>
                    <p class="text-xs text-slate-400 mt-1">Si separas por coma, puedes agregar múltiples lotes. Cuando guardes los cambios, quedará registrado quién lo modificó.</p>
                </div>

                <div class="flex-1 mt-4">
                    <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Historial de Lotes</label>
                    <div class="bg-slate-50 rounded-xl border border-slate-200 p-2 overflow-y-auto max-h-60">
                        <template x-if="!detailProduct.lote_history || detailProduct.lote_history.length === 0">
                            <div class="text-center text-sm text-slate-400 py-6">No hay historial de lotes registrado.</div>
                        </template>
                        <template x-if="detailProduct.lote_history && detailProduct.lote_history.length > 0">
                            <ul class="space-y-2">
                                <template x-for="(lh, idx) in detailProduct.lote_history" :key="idx">
                                    <li class="bg-white p-3 rounded-lg border border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2 shadow-sm">
                                        <div class="text-sm flex flex-wrap items-center gap-x-2">
                                            <div class="flex flex-col">
                                                <span><span class="text-slate-400 text-xs">Antes:</span> <span class="font-mono text-slate-600 line-through" x-text="lh.old_lote || '(vacío)'"></span></span>
                                                <span class="text-[10px] text-slate-400 line-through" x-show="lh.old_elab_date || lh.old_date" x-text="'📅 F.Elaboracion: ' + (lh.old_elab_date || lh.old_date)"></span>
                                                <span class="text-[10px] text-slate-400 line-through" x-show="lh.old_reinsp_date" x-text="'📅 F.Reinspeccion: ' + lh.old_reinsp_date"></span>
                                            </div>
                                            <span class="text-slate-300">→</span>
                                            <div class="flex flex-col">
                                                <span><span class="text-slate-400 text-xs">Ahora:</span> <span class="font-mono font-medium text-slate-800" x-text="lh.new_lote || '(vacío)'"></span></span>
                                                <span class="text-[10px] text-slate-500" x-show="lh.new_elab_date || lh.new_date" x-text="'📅 F.Elaboracion: ' + (lh.new_elab_date || lh.new_date)"></span>
                                                <span class="text-[10px] text-slate-500" x-show="lh.new_reinsp_date" x-text="'📅 F.Reinspeccion: ' + lh.new_reinsp_date"></span>
                                            </div>
                                            <div class="ml-2 pl-2 border-l border-orange-100 flex flex-col justify-center" x-show="lh.merma_kg">
                                                <span class="text-[10px] text-orange-500 font-bold">Merma</span>
                                                <span class="text-xs text-orange-600 font-bold" x-text="lh.merma_kg + 'kg'"></span>
                                            </div>
                                            <div class="ml-2 pl-2 border-l border-blue-100 flex flex-col justify-center max-w-[150px]" x-show="lh.notes">
                                                <span class="text-[10px] text-blue-500 font-bold">Nota</span>
                                                <span class="text-[10px] text-slate-500 italic truncate" :title="lh.notes" x-text="lh.notes"></span>
                                            </div>
                                        </div>
                                        <div class="text-right text-xs text-slate-500 flex flex-col">
                                            <span class="font-medium text-slate-600" x-text="lh.user"></span>
                                            <span x-text="lh.date || lh.timestamp"></span>
                                        </div>
                                    </li>
                                </template>
                            </ul>
                        </template>
                    </div>
                </div>
            </div>

            <!-- Modal Footer -->
            <div class="px-6 py-4 border-t border-slate-200 flex items-center justify-end gap-3 bg-slate-50">
                <button @click="showDetailModal = false"
                    class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-200 rounded-lg transition-colors">
                    Cancelar
                </button>
                <button @click="saveDetail()"
                    class="px-6 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium">
                    Guardar Cambios
                </button>
            </div>
        </div>
    </div>

    <!-- Toast Notification -->
    <div x-show="toastMessage" x-cloak
        x-transition:enter="transition ease-out duration-300"
        x-transition:enter-start="opacity-0 translate-y-2"
        x-transition:enter-end="opacity-100 translate-y-0"
        x-transition:leave="transition ease-in duration-200"
        x-transition:leave-start="opacity-100"
        x-transition:leave-end="opacity-0"
        class="fixed bottom-6 right-6 z-[9999] bg-emerald-600 text-white px-6 py-3 rounded-xl shadow-lg text-sm font-medium"
        x-text="toastMessage">
    </div>
</div>

<script>
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
        editLoteDateValue: '',
        editLoteReinspDateValue: '',
        editMermaValue: '',
        editNotesValue: '',
        editingHistoryNoteId: null,
        editHistoryNoteValue: '',

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
            
            this.$watch('mainTab', val => {
                if (val === 'historial_lotes' && this.loteHistory.length === 0) {
                    this.loadLoteHistory();
                }
            });
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

        
        async uploadLotesTemplate(event) {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/control/api/lotes/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await res.json();
                
                if (res.ok) {
                    alert('✅ ' + data.message);
                    this.loadProducts(this.currentPage);
                    if (this.mainTab === 'history') {
                         this.loadHistory();
                    }
                } else {
                    alert('❌ Error: ' + (data.error || 'Error subiendo archivo'));
                }
            } catch (err) {
                alert('❌ Error de red: ' + err);
            } finally {
                event.target.value = ''; // Reset input
            }
        },

        async uploadLotesTemplate(event) {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/control/api/lotes/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await res.json();
                
                if (res.ok) {
                    alert('✅ ' + data.message);
                    this.loadProducts(this.currentPage);
                    if (this.mainTab === 'history') {
                         this.loadHistory();
                    }
                } else {
                    alert('❌ Error: ' + (data.error || 'Error subiendo archivo'));
                }
            } catch (err) {
                alert('❌ Error de red: ' + err);
            } finally {
                event.target.value = ''; // Reset input
            }
        },

        normalizeIsoDate(dateStr) {
            const raw = (dateStr || '').toString().trim();
            if (!raw) return '';
            const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
            if (!m) return '';

            const y = parseInt(m[1], 10);
            const mo = parseInt(m[2], 10);
            const d = parseInt(m[3], 10);
            if (mo < 1 || mo > 12 || d < 1 || d > 31) return '';

            const dt = new Date(y, mo - 1, d);
            if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) return '';
            return raw;
        },

        computeReinspectionFromElab(elabDate) {
            const iso = this.normalizeIsoDate(elabDate);
            if (!iso) return '';

            const [yStr, mStr, dStr] = iso.split('-');
            const y = parseInt(yStr, 10);
            const m = parseInt(mStr, 10);
            const d = parseInt(dStr, 10);
            const targetYear = y + 1;

            const daysInTargetMonth = new Date(targetYear, m, 0).getDate();
            const safeDay = Math.min(d, daysInTargetMonth);
            return `${targetYear.toString().padStart(4, '0')}-${m.toString().padStart(2, '0')}-${safeDay.toString().padStart(2, '0')}`;
        },

        autoFillInlineReinspectionFromElab(force = false) {
            const suggested = this.computeReinspectionFromElab(this.editLoteDateValue);
            if (!suggested) return;
            if (force || !this.editLoteReinspDateValue) {
                this.editLoteReinspDateValue = suggested;
            }
        },

        autoFillDetailReinspectionFromElab(force = false) {
            if (!this.detailProduct) return;
            const suggested = this.computeReinspectionFromElab(this.detailProduct.lote_date);
            if (!suggested) return;
            if (force || !this.detailProduct.lote_reinspection_date) {
                this.detailProduct.lote_reinspection_date = suggested;
            }
        },

        async saveInlineLote(product) {
            this.autoFillInlineReinspectionFromElab();
            
            const mermaNum = parseFloat(this.editMermaValue);
            const hasMerma = !isNaN(mermaNum) && mermaNum > 0;
            const hasNotes = this.editNotesValue.trim().length > 0;

            if (
                !hasMerma &&
                !hasNotes &&
                this.editLoteValue === product.lote &&
                this.editLoteDateValue === (product.lote_date || '') &&
                this.editLoteReinspDateValue === (product.lote_reinspection_date || '')
            ) {
                // If the user didn't change anything and didn't add merma/notes, we'll STILL submit
                // but we will send force_history flag so it registers the movement anyway
            }
            
            try {
                const payload = {
                    lote: this.editLoteValue,
                    lote_date: this.editLoteDateValue,
                    lote_reinspection_date: this.editLoteReinspDateValue,
                    force_history: true
                };

                if (hasMerma) {
                    payload.merma_kg = mermaNum;
                }
                
                if (hasNotes) {
                    payload.notes_lote = this.editNotesValue.trim();
                }

                const res = await fetch(`/control/api/products/${product.product_id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.success) {
                    product.lote = this.editLoteValue;
                    product.lote_date = this.editLoteDateValue;
                    product.lote_reinspection_date = this.editLoteReinspDateValue;
                    this.toast('✅ Lote, F.Elaboracion y F.Reinspeccion actualizados');
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

        async saveHistoryNote(item) {
            try {
                const noteVal = this.editHistoryNoteValue.trim();
                if (noteVal === (item.notes || '')) {
                    this.editingHistoryNoteId = null;
                    return;
                }
                
                const payload = {
                    date: item.date || item.timestamp,
                    notes: noteVal
                };

                const res = await fetch(`/control/api/lote-history/${item.product_id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.success) {
                    item.notes = noteVal;
                    this.toast('✅ Nota actualizada');
                } else {
                    throw new Error(data.error || 'Unknown error');
                }
            } catch (e) {
                console.error('Error saving history note:', e);
                this.toast('❌ Error al actualizar la nota', 'error');
            }
            this.editingHistoryNoteId = null;
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
                dp.lote_date = dp.lote_date || '';
                dp.lote_reinspection_date = dp.lote_reinspection_date || '';
                this.detailProduct = dp;
                this.autoFillDetailReinspectionFromElab();
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
                this.autoFillDetailReinspectionFromElab();
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
                        lote_date: this.detailProduct.lote_date,
                        lote_reinspection_date: this.detailProduct.lote_reinspection_date,
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
</script>
{% endblock %}
