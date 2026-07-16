# Context: Template Designer Panel — Fixes & Enhancements

## Date: 2026-03-06

## 1. Initial Syntax Fix (loadPreset missing `this.elements = [`)

The `loadPreset()` method was missing `this.elements = [`, causing a `SyntaxError` that
prevented the entire `templateDesigner()` function from being defined. Fixed by adding
the missing assignment. Debug error alert handlers were also removed.

## 2. Warehouse-Locked Canvas Sizes

Template canvas dimensions are locked per warehouse:
- Almacen1 (`01`) → 151 x 101 mm
- Almacen2 (`02`) → 200 x 150 mm

Dimension inputs are disabled with a lock icon when the user belongs to a known warehouse.

## 3. Undo / Redo System (NEW)

Full undo/redo with up to 60 history states:
- **Ctrl+Z** → Undo
- **Ctrl+Shift+Z** / **Ctrl+Y** → Redo
- Toolbar buttons with SVG arrows, disabled when stack is empty
- State serialized as JSON snapshot of all elements (excludes `_uid`)
- New actions clear the redo stack
- Initial snapshot taken after `init()`

## 4. Live Data Preview on Canvas (NEW)

A "Datos en Vivo" bar sits between the toolbar and the designer body:
- Search products by code or name (debounced, with dropdown)
- Select a product → real data populates all template fields on the canvas
- `elementDisplayText()` prioritizes `liveDataFields[field]` when active
- Clear button (×) reverts to placeholder display
- Green indicator + product name badge when active
- Feeds into Preview modal's product code field

### Backend API

New endpoint added to `sga_web/routes/templates.py`:

```
GET /templates/api/product_data/<product_id>
```

Returns JSON with:
- `fields` — dict mapping template field names to real values
- `pictogram_urls` — list of image paths for the product's GHS pictograms
- `product_name_display` — truncated name for the UI badge

## Files Changed

| File | Change |
|------|--------|
| `sga_web/templates/templates/designer.html` | Undo/redo engine, live data bar + search, toolbar buttons, updated `elementDisplayText()`, `markDirty()` pushes undo snapshots |
| `sga_web/routes/templates.py` | Added `/api/product_data/<product_id>` endpoint |

## How to Verify

1. Start: `python sga_web/app.py`
2. Open any template in the designer
3. **Undo/Redo**: Move an element, press Ctrl+Z — element returns to original position. Ctrl+Shift+Z to redo.
4. **Live Data**: Type a product code in the "Datos en Vivo" bar → click "Cargar". All placeholder text on the canvas should show real product values. Click × to clear.
