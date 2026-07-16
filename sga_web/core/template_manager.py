"""
Template Manager for Label Templates
Handles CRUD operations for label template JSON files.
"""

import os
import json
import uuid
from datetime import datetime
import re


class TemplateManager:
    """Manages label templates stored as JSON files."""

    # Available data fields that can be placed on a template
    AVAILABLE_FIELDS = {
        "process_barcode": {
            "label": "Código de Proceso",
            "type": "barcode",
            "default_value": "01-ENVASADO",
        },
        "internal_code_barcode": {
            "label": "Código Interno (Barcode)",
            "type": "barcode",
        },
        "internal_code_text": {"label": "Código Interno (Texto)", "type": "text"},
        "product_name": {"label": "Nombre del Producto", "type": "text"},
        "signal_word": {"label": "Palabra de Señal", "type": "text"},
        "cas_number": {"label": "Número CAS", "type": "text"},
        "h_statements": {"label": "Indicaciones de Peligro (H)", "type": "multiline"},
        "p_statements": {"label": "Consejos de Prudencia (P)", "type": "multiline"},
        "h_header": {
            "label": "Encabezado Indicaciones",
            "type": "static",
            "default_value": "INDICACIONES DE PELIGRO:",
        },
        "p_header": {
            "label": "Encabezado Consejos",
            "type": "static",
            "default_value": "CONSEJOS DE PRUDENCIA:",
        },
        "elab_date_label": {
            "label": "Etiqueta F.Elaboración",
            "type": "static",
            "default_value": "F.ELABORACION:",
        },
        "elab_date_value": {"label": "Valor F.Elaboración", "type": "text"},
        "reinsp_date_label": {
            "label": "Etiqueta F.Reinspección",
            "type": "static",
            "default_value": "F.REINSPECCION:",
        },
        "reinsp_date_value": {"label": "Valor F.Reinspección", "type": "text"},
        "lote_label": {
            "label": "Etiqueta LOTE",
            "type": "static",
            "default_value": "LOTE:",
        },
        "lote_value": {"label": "Valor LOTE", "type": "text"},
        "batch_barcode": {"label": "Código de Barras LOTE", "type": "barcode"},
        "peso_bruto_label": {
            "label": "Etiqueta Peso Bruto",
            "type": "static",
            "default_value": "PESO BRUTO:",
        },
        "peso_bruto_value": {"label": "Valor Peso Bruto", "type": "text"},
        "peso_tara_label": {
            "label": "Etiqueta Peso Tara",
            "type": "static",
            "default_value": "PESO TARA:",
        },
        "peso_tara_value": {"label": "Valor Peso Tara", "type": "text"},
        "peso_neto_label": {
            "label": "Etiqueta Peso Neto",
            "type": "static",
            "default_value": "PESO NETO:",
        },
        "peso_neto_value": {"label": "Valor Peso Neto", "type": "text"},
        "net_weight_barcode": {
            "label": "Código de Barras Peso Neto",
            "type": "barcode",
        },
        "gross_weight_barcode": {
            "label": "Código de Barras Peso Bruto",
            "type": "barcode",
        },
        "address_footer": {
            "label": "Dirección Pie de Página",
            "type": "static",
            "default_value": "QUIMICA BOSS San Agustin 759 Col. El Briseño, Zapopan, Jalisco, México. CP 45236 Tel: 36 84 05 05",
        },
        "separator_line": {"label": "Línea Separadora", "type": "line"},
        "static_text": {
            "label": "Texto Libre",
            "type": "static",
            "default_value": "Texto",
        },
        "ghs_pictograms": {
            "label": "Pictogramas del Producto",
            "type": "pictogram_group",
        },
        "company_logo": {"label": "Logo Empresa", "type": "image"},
        "ghs_pictograms_locked": {
            "label": "Pictogramas Bloqueados",
            "type": "pictogram_group_locked",
        },
    }

    def __init__(self, templates_dir=None):
        if templates_dir is None:
            base = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            templates_dir = os.path.join(base, "label_templates")
        self.templates_dir = templates_dir
        os.makedirs(self.templates_dir, exist_ok=True)

    def _template_path(self, template_id):
        return os.path.join(self.templates_dir, f"{template_id}.json")

    def list_templates(self):
        """Return list of all template summaries."""
        templates = []
        template_id_pattern = re.compile(r"^[a-f0-9]{8}$")
        seen_ids = set()
        for filename in os.listdir(self.templates_dir):
            if filename.endswith(".json"):
                try:
                    with open(
                        os.path.join(self.templates_dir, filename),
                        "r",
                        encoding="utf-8",
                    ) as f:
                        data = json.load(f)

                    template_id = data.get("id")
                    # Ignore backup/auxiliary JSON files and malformed template ids.
                    # Real templates use 8-char hex IDs (e.g., ad2c37a6.json).
                    if not isinstance(
                        template_id, str
                    ) or not template_id_pattern.match(template_id):
                        continue
                    if template_id in seen_ids:
                        continue
                    seen_ids.add(template_id)

                    templates.append(
                        {
                            "id": template_id,
                            "name": data.get("name", "Sin nombre"),
                            "width_mm": data.get("width_mm", 150),
                            "height_mm": data.get("height_mm", 100),
                            "rotation": data.get("rotation", 0),
                            "element_count": len(data.get("elements", [])),
                            "created_at": data.get("created_at", ""),
                            "updated_at": data.get("updated_at", ""),
                        }
                    )
                except (json.JSONDecodeError, IOError):
                    continue
        templates.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
        return templates

    def get_template(self, template_id):
        """Get a template by ID."""
        path = self._template_path(template_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def save_template(self, data):
        """Create or update a template. Returns the saved template data."""
        now = datetime.now().isoformat()

        if not data.get("id"):
            data["id"] = str(uuid.uuid4())[:8]
            data["created_at"] = now

        data["updated_at"] = now

        # Validate required fields
        if not data.get("name"):
            data["name"] = "Plantilla sin nombre"
        if not data.get("width_mm"):
            data["width_mm"] = 200
        if not data.get("height_mm"):
            data["height_mm"] = 155
        if "elements" not in data:
            data["elements"] = []

        path = self._template_path(data["id"])

        # Preserve created_at from existing template if updating
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if "created_at" not in data or not data["created_at"]:
                    data["created_at"] = existing.get("created_at", now)
            except Exception:
                pass

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return data

    def delete_template(self, template_id):
        """Delete a template by ID. Returns True if deleted."""
        path = self._template_path(template_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def duplicate_template(self, template_id):
        """Duplicate a template. Returns the new template data."""
        original = self.get_template(template_id)
        if not original:
            return None

        new_data = original.copy()
        new_data["id"] = str(uuid.uuid4())[:8]
        new_data["name"] = f"{original.get('name', 'Plantilla')} (copia)"
        now = datetime.now().isoformat()
        new_data["created_at"] = now
        new_data["updated_at"] = now

        return self.save_template(new_data)

    def get_available_fields(self):
        """Return the available fields dictionary for the frontend."""
        return self.AVAILABLE_FIELDS
